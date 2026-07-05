"""
ETL: NDS/CSV → DDS (Dimensional Data Store) trên SQLite.

Nạp dữ liệu vận hành từ CSV vào star schema (dim_product, dim_warehouse,
dim_time, fact_inventory_smi, dds_packing_config).

Thay cho ETL PL/pgSQL cũ (database/dds/02_etl_procedures.sql) vốn viết cho
PostgreSQL. Logic bám sát CsvOptimizationDataRepository để bảo đảm dữ liệu
DDS TRÙNG KHỚP với đường CSV → không làm đổi kết quả tối ưu MA.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

from backend.core.database import engine_dds, SessionLocalDDS, BaseDDS
from backend.data_access.models_dds import (
    DimProduct, DimWarehouse, DimTime,
    FactInventorySMI, DDSPackingConfig, DDSModelParameters,
)


def _read(dir_: Path, name: str, **kw) -> pd.DataFrame:
    return pd.read_csv(dir_ / name, **kw)


def run_etl(data_dir: str, hv: float = 9999.0) -> Dict[str, int]:
    """
    Nạp toàn bộ DDS từ CSV. Idempotent: xóa sạch bảng DDS rồi nạp lại.

    Trả về dict đếm số bản ghi mỗi bảng.
    """
    d = Path(data_dir)

    # Bảo đảm bảng tồn tại
    BaseDDS.metadata.create_all(bind=engine_dds)

    # ── Đọc CSV (giống csv_repository) ────────────────────────────────
    products   = _read(d, "product.csv", dtype=str)
    warehouses = _read(d, "warehouse.csv", dtype=str)
    periods    = _read(d, "time_period.csv")
    inv_begin  = _read(d, "inventory_begin.csv", dtype={"product_id": str, "warehouse_id": str})
    inv_flow   = _read(d, "inventory_flow.csv", dtype={"product_id": str, "warehouse_id": str})
    capacity   = _read(d, "vendor_capacity.csv", dtype={"product_id": str})
    unit_cost  = _read(d, "unit_cost.csv", dtype={"product_id": str, "warehouse_id": str})
    packing    = _read(d, "packing_details.csv", dtype={"product_id": str})
    box_ship   = _read(d, "box_shipment.csv", dtype={"warehouse_id": str})

    # Sản phẩm "active" = có mặt trong inventory_flow (giống csv_repository)
    active_products = set(inv_flow["product_id"].str.strip().unique())

    db = SessionLocalDDS()
    try:
        # ── Xóa sạch (idempotent) — thứ tự tôn trọng FK ──────────────
        db.query(FactInventorySMI).delete()
        db.query(DDSPackingConfig).delete()
        db.query(DimProduct).delete()
        db.query(DimWarehouse).delete()
        db.query(DimTime).delete()
        db.query(DDSModelParameters).delete()
        db.commit()

        today = date.today()

        # ── DIM_PRODUCT (chỉ SP active) ──────────────────────────────
        prod_sk: Dict[str, int] = {}
        for _, row in products.iterrows():
            pid = str(row["product_id"]).strip()
            if pid not in active_products:
                continue
            dp = DimProduct(
                product_id=pid,
                item_class=str(row.get("item_class", "") or ""),
                product_series=str(row.get("product_series", "") or ""),
                product_style=str(row.get("product_style", "") or ""),
                product_size=str(row.get("product_size", "") or ""),
                pack_kind="STANDARD",
                effective_date=today,
                is_current=True,
            )
            db.add(dp)
        db.flush()
        for dp in db.query(DimProduct).all():
            prod_sk[dp.product_id] = dp.product_sk

        # ── DIM_WAREHOUSE ────────────────────────────────────────────
        wh_sk: Dict[str, int] = {}
        for _, row in warehouses.iterrows():
            wid = str(row["warehouse_id"]).strip()
            dw = DimWarehouse(
                warehouse_id=wid,
                market_code=str(row.get("market_code", "") or ""),
                effective_date=today,
                is_current=True,
            )
            db.add(dw)
        db.flush()
        for dw in db.query(DimWarehouse).all():
            wh_sk[dw.warehouse_id] = dw.warehouse_sk

        # ── DIM_TIME ─────────────────────────────────────────────────
        time_sk: Dict[int, int] = {}
        for _, row in periods.iterrows():
            t = int(row["time_period"])
            dt = DimTime(
                time_period=t,
                start_date=pd.to_datetime(row["start_date"]).date(),
                end_date=pd.to_datetime(row["end_date"]).date(),
                week=int(row["week"]) if "week" in row and pd.notna(row["week"]) else None,
                month=int(row["month"]) if "month" in row and pd.notna(row["month"]) else None,
                year=int(row["year"]) if "year" in row and pd.notna(row["year"]) else None,
                is_current=False,
            )
            db.add(dt)
        db.flush()
        for dt in db.query(DimTime).all():
            time_sk[dt.time_period] = dt.time_period_sk

        # ── Chuẩn bị lookup cho FACT ─────────────────────────────────
        # BI[(i,j)]
        bi_map: Dict[Tuple[str, str], float] = {}
        for _, row in inv_begin.iterrows():
            bi_map[(str(row["product_id"]), str(row["warehouse_id"]))] = float(row["beginning_inventory"])

        # CAP[(i,t)]
        cap_map: Dict[Tuple[str, int], float] = {}
        for _, row in capacity.iterrows():
            cap_map[(str(row["product_id"]), int(row["time_period"]))] = float(row["capacity"])

        # cost[(i,j,t)]
        cost_map: Dict[Tuple[str, str, int], Tuple[float, float, float, float]] = {}
        for _, row in unit_cost.iterrows():
            cost_map[(str(row["product_id"]), str(row["warehouse_id"]), int(row["time_period"]))] = (
                float(row["overstock_cost"]), float(row["shortage_cost"]),
                float(row["backlog_cost"]), float(row["penalty_cost"]),
            )

        # CP[(i,j)] — replicate logic box_shipment→packing của csv_repository
        packing_indexed = packing.reset_index(drop=True)
        packing_indexed.index = packing_indexed.index + 1
        pd_id_to_product: Dict[int, Tuple[str, int]] = {}
        for idx, row in packing_indexed.iterrows():
            pd_id_to_product[int(idx)] = (str(row["product_id"]), int(row["pack_multiple"]))
        cp_map: Dict[Tuple[str, str], int] = {}
        active_ship = box_ship[box_ship["is_active"].astype(str).str.lower() == "true"]
        for _, row in active_ship.iterrows():
            pdid = int(row["packing_details_id"])
            wid = str(row["warehouse_id"])
            if pdid in pd_id_to_product:
                pid, mult = pd_id_to_product[pdid]
                cp_map[(pid, wid)] = mult

        # ── FACT_INVENTORY_SMI — 1 dòng / (i,j,t) từ inventory_flow ───
        n_fact = 0
        for _, row in inv_flow.iterrows():
            pid = str(row["product_id"]).strip()
            wid = str(row["warehouse_id"]).strip()
            t = int(row["time_period"])
            if pid not in prod_sk or wid not in wh_sk or t not in time_sk:
                continue
            co, cs, cb, cp = cost_map.get((pid, wid, t), (0.1, 0.5, 1500.0, 500.0))
            fact = FactInventorySMI(
                product_sk=prod_sk[pid],
                warehouse_sk=wh_sk[wid],
                time_period_sk=time_sk[t],
                beginning_inventory_qty=int(bi_map.get((pid, wid), 0)),
                delta_inventory_qty=int(row["inventory_fluctuation"]),
                firm_capacity_qty=int(cap_map.get((pid, t), 0)),
                inventory_ceiling=int(row["inventory_ceiling"]),
                inventory_floor=int(row["inventory_floor"]),
                cost_overstock=co, cost_shortage=cs,
                cost_backorder=cb, cost_penalty=cp,
                applied_pack_multiple=cp_map.get((pid, wid)),
            )
            db.add(fact)
            n_fact += 1
        db.flush()

        # ── DDS_PACKING_CONFIG — CP[(i,j)] ───────────────────────────
        n_pack = 0
        for (pid, wid), mult in cp_map.items():
            if pid in prod_sk and wid in wh_sk:
                db.add(DDSPackingConfig(
                    product_sk=prod_sk[pid], warehouse_sk=wh_sk[wid],
                    box_id=0, pack_multiple=mult, is_active=True,
                ))
                n_pack += 1

        # ── DDS_MODEL_PARAMETERS — HV ────────────────────────────────
        db.add(DDSModelParameters(param_name="HV", param_value=hv,
                                  param_description="High value constant for linearization"))

        db.commit()

        counts = {
            "dim_product": len(prod_sk),
            "dim_warehouse": len(wh_sk),
            "dim_time": len(time_sk),
            "fact_inventory_smi": n_fact,
            "dds_packing_config": n_pack,
        }
        print(f"[DDS ETL] Nạp xong: {counts}", flush=True)
        return counts

    finally:
        db.close()
