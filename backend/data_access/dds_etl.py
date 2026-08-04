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
    FactInventorySMI, DDSPackingConfig, DDSModelParameters, FactPltInput,
    DimScenario, DimRun, FactModelResult, FactPltResult, FactRunSummary,
)

# Mapping WH01-WH06 → State code trong FGPs_distance.csv (khớp ma_adapter.py)
_WH_TO_STATE = {
    "WH01": "MI", "WH02": "OH", "WH03": "IN",
    "WH04": "IL", "WH05": "KY", "WH06": "MO",
}
_TC_DEFAULT = 1.2       # 40ft Dry container (container_pricing.csv row 2)
_LT_OA_DEFAULT = 8      # week_lead_time từ oa_lead_time.csv (đồng nhất = 8)


def _read(dir_: Path, name: str, **kw) -> pd.DataFrame:
    return pd.read_csv(dir_ / name, **kw)


# Trường số bắt buộc theo từng file — dùng để validate trước khi nạp DDS.
# Tách riêng theo file thay vì gộp chung để báo lỗi rõ nguồn gốc.
_NUMERIC_CHECKS: Dict[str, list] = {
    "inventory_flow.csv": ["time_period", "inventory_fluctuation", "inventory_ceiling", "inventory_floor"],
    "inventory_begin.csv": ["beginning_inventory"],
    "unit_cost.csv": ["overstock_cost", "shortage_cost", "backlog_cost", "penalty_cost"],
    "vendor_capacity.csv": ["capacity"],
}
# Trường phải >= 0 (không thể âm về mặt nghiệp vụ) — chỉ cảnh báo, không loại dòng.
_NON_NEGATIVE_CHECKS: Dict[str, list] = {
    "inventory_flow.csv": ["inventory_ceiling", "inventory_floor"],
    "inventory_begin.csv": ["beginning_inventory"],
    "vendor_capacity.csv": ["capacity"],
}


def _validate_numeric(df: pd.DataFrame, fname: str, report: Dict) -> Dict[str, int]:
    """
    Kiểm tra các trường số của 1 file: đếm dòng không ép kiểu được (text/rỗng/NaN)
    và dòng có giá trị âm bất thường. Chỉ log/đếm — KHÔNG chỉnh sửa df ở đây.
    """
    cols = _NUMERIC_CHECKS.get(fname, [])
    neg_cols = _NON_NEGATIVE_CHECKS.get(fname, [])
    bad_type_total = 0
    for c in cols:
        if c not in df.columns:
            continue
        numeric = pd.to_numeric(df[c], errors="coerce")
        bad_mask = numeric.isna() & df[c].notna()
        n_bad = int(bad_mask.sum())
        if n_bad:
            bad_type_total += n_bad
            print(f"[DDS ETL][VALIDATE] {fname}.{c}: {n_bad} dòng không phải số hợp lệ "
                  f"(mẫu: {list(df.loc[bad_mask, c].unique()[:5])})", flush=True)
    for c in neg_cols:
        if c not in df.columns:
            continue
        numeric = pd.to_numeric(df[c], errors="coerce")
        n_neg = int((numeric < 0).sum())
        if n_neg:
            print(f"[DDS ETL][VALIDATE] {fname}.{c}: {n_neg} dòng có giá trị âm bất thường", flush=True)
            report.setdefault("negative_value_warnings", {})[f"{fname}.{c}"] = n_neg
    report.setdefault("bad_type_rows", {})[fname] = bad_type_total
    return {"bad_type_rows": bad_type_total}


def _clean_inventory_flow(df: pd.DataFrame, report: Dict) -> pd.DataFrame:
    """
    Bước làm sạch minh họa: ép kiểu số cho inventory_flow.csv (file trung tâm
    nhất của ETL — tạo FACT_INVENTORY_SMI) và loại các dòng không ép kiểu được
    thay vì để ETL crash. Trên bộ dữ liệu hiện tại không có dòng nào bị loại
    (đã verify: 0/35450 dòng lỗi kiểu số) — cơ chế được giữ lại để ETL vẫn an
    toàn nếu lần trích xuất dữ liệu doanh nghiệp sau này có sai sót.
    """
    cols = _NUMERIC_CHECKS["inventory_flow.csv"]
    numeric_df = df[cols].apply(pd.to_numeric, errors="coerce")
    bad_mask = numeric_df.isna().any(axis=1)
    n_bad = int(bad_mask.sum())
    report["inventory_flow_rows_dropped"] = n_bad
    if n_bad:
        print(f"[DDS ETL][CLEAN] inventory_flow.csv: loại {n_bad} dòng lỗi kiểu số trước khi nạp DDS", flush=True)
        df = df.loc[~bad_mask].reset_index(drop=True)
    return df


def run_etl(data_dir: str, hv: float = 9999.0) -> Dict[str, int]:
    """
    Nạp toàn bộ DDS từ CSV. Idempotent: xóa sạch bảng DDS rồi nạp lại.

    Trả về dict đếm số bản ghi mỗi bảng, kèm "data_quality_report" (số dòng
    lỗi kiểu số/giá trị âm phát hiện khi validate, số dòng bị loại khi clean).
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

    # ── Validate dữ liệu số trước khi nạp (log-only, không đổi hành vi) ──
    dq_report: Dict = {}
    _validate_numeric(inv_flow, "inventory_flow.csv", dq_report)
    _validate_numeric(inv_begin, "inventory_begin.csv", dq_report)
    _validate_numeric(unit_cost, "unit_cost.csv", dq_report)
    _validate_numeric(capacity, "vendor_capacity.csv", dq_report)

    # ── Clean: ép kiểu + loại dòng lỗi cho file trung tâm nhất của ETL ───
    inv_flow = _clean_inventory_flow(inv_flow, dq_report)

    # ── Đọc dữ liệu vận chuyển/PLT (giống ma_adapter.CSVDataLoader) ────
    # oa_lead_time.csv: warehouse_id dạng số (1-6) → map sang WH01-WH06
    oa_lead    = _read(d, "oa_lead_time.csv")
    plt_lead   = _read(d, "plt_lead_time.csv")
    distance   = _read(d, "FGPs_distance.csv", index_col="State")
    container  = _read(d, "container_pricing.csv")

    _wh_num_to_id = {str(i + 1): f"WH0{i + 1}" for i in range(6)}

    # LT_OA[wh]: thời gian giao từ kho trung tâm, theo kho
    lt_oa_map: Dict[str, int] = {}
    for _, row in oa_lead.iterrows():
        wid = _wh_num_to_id.get(str(int(row["warehouse_id"])))
        if wid:
            lt_oa_map[wid] = int(row["week_lead_time"])

    # LT_PLT[(from,to)]: thời gian điều chuyển ngang, theo cặp kho
    lt_plt_map: Dict[Tuple[str, str], int] = {}
    for _, row in plt_lead.iterrows():
        frm = _wh_num_to_id.get(str(int(row["from_warehouse_id"])))
        to  = _wh_num_to_id.get(str(int(row["to_warehouse_id"])))
        if frm and to:
            lt_plt_map[(frm, to)] = int(row["lead_time_weeks"])

    # TC: cước container 40ft Dry (USD/km), hằng số toàn cục
    _tc_row = container[container["Container_Type"] == "40ft Dry"]
    tc_value = float(_tc_row.iloc[0]["Base_Rate_USD_per_km"]) if not _tc_row.empty else _TC_DEFAULT

    # Sản phẩm "active" = có mặt trong inventory_flow (giống csv_repository)
    active_products = set(inv_flow["product_id"].str.strip().unique())

    db = SessionLocalDDS()
    try:
        # ── Xóa sạch (idempotent) — thứ tự tôn trọng FK ──────────────
        db.query(FactInventorySMI).delete()
        db.query(DDSPackingConfig).delete()
        db.query(FactPltInput).delete()
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
                lt_oa_weeks=lt_oa_map.get(wid, _LT_OA_DEFAULT),
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

        # ── FACT_PLT_INPUT — LT_PLT + khoảng cách theo cặp kho ────────
        n_plt_in = 0
        for wh_i in warehouses["warehouse_id"].astype(str):
            for wh_j in warehouses["warehouse_id"].astype(str):
                if wh_i == wh_j or wh_i not in wh_sk or wh_j not in wh_sk:
                    continue
                lt_plt = lt_plt_map.get((wh_i, wh_j))
                if lt_plt is None:
                    continue
                s_i, s_j = _WH_TO_STATE.get(wh_i), _WH_TO_STATE.get(wh_j)
                dist_km = None
                if s_i and s_j and s_i in distance.index and s_j in distance.columns:
                    dist_km = float(distance.loc[s_i, s_j])
                db.add(FactPltInput(
                    from_warehouse_sk=wh_sk[wh_i], to_warehouse_sk=wh_sk[wh_j],
                    lt_plt_weeks=lt_plt, distance_km=dist_km,
                ))
                n_plt_in += 1

        # ── DDS_MODEL_PARAMETERS — HV + TC ────────────────────────────
        db.add(DDSModelParameters(param_name="HV", param_value=hv,
                                  param_description="High value constant for linearization"))
        db.add(DDSModelParameters(param_name="TC", param_value=tc_value,
                                  param_description="Chi phí vận chuyển ngang (USD/km, container 40ft Dry)"))

        db.commit()

        counts = {
            "dim_product": len(prod_sk),
            "dim_warehouse": len(wh_sk),
            "dim_time": len(time_sk),
            "fact_inventory_smi": n_fact,
            "dds_packing_config": n_pack,
            "fact_plt_input": n_plt_in,
            "data_quality_report": dq_report,
        }
        print(f"[DDS ETL] Nạp xong: {counts}", flush=True)
        return counts

    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════
#  ETL KẾT QUẢ: NDS (optimization_result / plt / summary) → DDS
#  Nạp nhóm bảng kết quả (DIM_SCENARIO, DIM_RUN, FACT_*_RESULT, FACT_RUN_SUMMARY).
#  Bám theo các surrogate key của dim đã có (product/warehouse/time).
# ══════════════════════════════════════════════════════════════════════

def run_result_etl(run_id: int | None = None) -> Dict[str, int]:
    """
    ETL kết quả tối ưu từ NDS sang DDS.

    run_id=None: backfill TẤT CẢ run (xóa sạch nhóm bảng kết quả rồi nạp lại).
    run_id=<int>: chỉ nạp/cập nhật 1 run (idempotent — xóa dòng cũ của run đó).

    Chỉ đọc NDS + ghi DDS, KHÔNG đụng CSV/MA/số liệu tối ưu.
    """
    from backend.core.database import SessionLocal  # NDS session
    from backend.data_access.models_nds import (
        Scenario, OptimizationRun, OptimizationResult, OptimizationPLT,
        DssKPI, DssRunSummary,
    )

    BaseDDS.metadata.create_all(bind=engine_dds)

    nds = SessionLocal()
    dds = SessionLocalDDS()
    try:
        # ── Lookup surrogate key từ dim đã có trong DDS ──────────────
        prod_sk = {dp.product_id: dp.product_sk for dp in dds.query(DimProduct).all()}
        wh_sk   = {dw.warehouse_id: dw.warehouse_sk for dw in dds.query(DimWarehouse).all()}
        time_sk = {dt.time_period: dt.time_period_sk for dt in dds.query(DimTime).all()}

        # ── Chọn danh sách run cần ETL ───────────────────────────────
        if run_id is None:
            runs = nds.query(OptimizationRun).all()
            # Xóa sạch toàn bộ nhóm kết quả (thứ tự tôn trọng FK)
            dds.query(FactModelResult).delete()
            dds.query(FactPltResult).delete()
            dds.query(FactRunSummary).delete()
            dds.query(DimRun).delete()
            dds.query(DimScenario).delete()
            dds.commit()
        else:
            runs = nds.query(OptimizationRun).filter(OptimizationRun.run_id == run_id).all()
            # Xóa dòng cũ của run này (idempotent)
            old = dds.query(DimRun).filter(DimRun.run_id == run_id).first()
            if old:
                dds.query(FactModelResult).filter(FactModelResult.run_sk == old.run_sk).delete()
                dds.query(FactPltResult).filter(FactPltResult.run_sk == old.run_sk).delete()
                dds.query(FactRunSummary).filter(FactRunSummary.run_sk == old.run_sk).delete()
                dds.delete(old)
                dds.commit()

        n_scn = n_run = n_res = n_plt = n_sum = 0
        scn_sk_cache: Dict[int, int] = {
            ds.scenario_id: ds.scenario_sk for ds in dds.query(DimScenario).all()
        }

        for run in runs:
            # ── DIM_SCENARIO (tạo nếu chưa có) ───────────────────────
            scn_sk = scn_sk_cache.get(run.scenario_id)
            if scn_sk is None:
                scn = nds.query(Scenario).filter(Scenario.scenario_id == run.scenario_id).first()
                dim_scn = DimScenario(
                    scenario_id=run.scenario_id,
                    scenario_name=(scn.scenario_name if scn else f"Scenario {run.scenario_id}"),
                    scenario_type=("baseline" if (scn and scn.is_baseline) else "scenario"),
                    is_baseline=bool(scn.is_baseline) if scn else False,
                )
                dds.add(dim_scn)
                dds.flush()
                scn_sk = dim_scn.scenario_sk
                scn_sk_cache[run.scenario_id] = scn_sk
                n_scn += 1

            # ── DIM_RUN ──────────────────────────────────────────────
            dim_run = DimRun(
                run_id=run.run_id,
                scenario_sk=scn_sk,
                solver_status=run.solver_status,
                solver_name="Memetic (GA-ALNS)",
                objective_value=run.objective_value,
                solve_time_seconds=run.solve_time_seconds,
                run_time=run.run_time,
            )
            dds.add(dim_run)
            dds.flush()
            run_sk = dim_run.run_sk
            n_run += 1

            # ── FACT_MODEL_RESULT (từ optimization_result) ───────────
            for r in nds.query(OptimizationResult).filter(OptimizationResult.run_id == run.run_id).all():
                dds.add(FactModelResult(
                    run_sk=run_sk,
                    product_sk=prod_sk.get(r.product_id),
                    warehouse_sk=wh_sk.get(r.warehouse_id),
                    time_period_sk=time_sk.get(r.time_period),
                    q_case_pack=r.q_case_pack,
                    r_residual_units=r.r_residual_units,
                    net_inventory=r.net_inventory,
                    backorder_qty=r.backorder_qty,
                    overstock_qty=r.overstock_qty,
                    shortage_qty=r.shortage_qty,
                    penalty_flag=r.penalty_flag,
                ))
                n_res += 1

            # ── FACT_PLT_RESULT (từ optimization_plt) ────────────────
            for p in nds.query(OptimizationPLT).filter(OptimizationPLT.run_id == run.run_id).all():
                dds.add(FactPltResult(
                    run_sk=run_sk,
                    product_sk=prod_sk.get(p.product_id),
                    from_warehouse_sk=wh_sk.get(p.from_warehouse_id),
                    to_warehouse_sk=wh_sk.get(p.to_warehouse_id),
                    time_period_sk=time_sk.get(p.time_period),
                    qty=p.qty,
                ))
                n_plt += 1

            # ── FACT_RUN_SUMMARY (từ dss_kpi + dss_run_summary) ──────
            kpi = nds.query(DssKPI).filter(DssKPI.run_id == run.run_id).first()
            summ = nds.query(DssRunSummary).filter(DssRunSummary.run_id == run.run_id).first()
            if kpi or summ:
                dds.add(FactRunSummary(
                    run_sk=run_sk,
                    total_cost=(kpi.total_cost if kpi else None),
                    baseline_cost=(summ.baseline_cost if summ else None),
                    opt_cost=(summ.opt_cost if summ else None),
                    savings=(summ.savings if summ else None),
                    savings_pct=(summ.savings_pct if summ else None),
                    total_backorder=(kpi.total_backorder if kpi else None),
                    total_overstock=(kpi.total_overstock if kpi else None),
                    total_shortage=(kpi.total_shortage if kpi else None),
                    total_penalty=(kpi.total_penalty if kpi else None),
                    si_mean=(summ.si_mean if summ else None),
                    ss_below_count=(summ.ss_below_count if summ else None),
                    n_changes=(summ.n_changes if summ else None),
                ))
                n_sum += 1

            dds.commit()

        counts = {
            "dim_scenario": n_scn, "dim_run": n_run,
            "fact_model_result": n_res, "fact_plt_result": n_plt,
            "fact_run_summary": n_sum,
        }
        print(f"[DDS Result ETL] Nạp xong: {counts}", flush=True)
        return counts

    finally:
        nds.close()
        dds.close()
