"""
backend/domain/dds_adapter.py
==============================
Convert DDS (Dimensional Data Store, SQLite dds.db) → MA Problem object,
song song với ma_adapter.py (đọc CSV). KHÔNG đụng đến GA/ALNS/decoder/
objective — chỉ là lớp chuyển đổi dữ liệu, tương đương build_problem()
nhưng nguồn là DDS thay vì CSV.

Mục tiêu: verify DDS chứa đủ và đúng dữ liệu để nuôi MA solver, chứng minh
kiến trúc "DDS phục vụ trực tiếp tối ưu hóa" đúng như Chương 5 luận văn.

Mặc định MA vẫn dùng CSV (ma_adapter.py) — module này KHÔNG thay đổi hành
vi hiện tại trừ khi được gọi tường minh.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.data_access.models_dds import (
    DimProduct, DimWarehouse, DimTime, FactInventorySMI,
    DDSPackingConfig, DDSModelParameters, FactPltInput,
)

import sys
from pathlib import Path
_MA_DIR = Path(__file__).resolve().parent.parent / "ma"
if str(_MA_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_MA_DIR.parent))
from ma.core.problem import Problem

LT_OA_DEFAULT = 8
TC_DEFAULT = 1.2


class DDSDataLoader:
    """Load và cache dữ liệu DDS cần thiết cho MA adapter (1 lần / session)."""

    def __init__(self, db: Session):
        self.db = db
        self._load()

    def _load(self):
        self.warehouses: List[str] = [
            w.warehouse_id for w in
            self.db.query(DimWarehouse).filter(DimWarehouse.is_current == True).all()
        ]
        self.periods: List[int] = sorted(
            t.time_period for t in self.db.query(DimTime).all()
        )

        # warehouse_id -> (warehouse_sk, lt_oa_weeks)
        self.wh_info: Dict[str, Tuple[int, int]] = {
            w.warehouse_id: (w.warehouse_sk, w.lt_oa_weeks or LT_OA_DEFAULT)
            for w in self.db.query(DimWarehouse).filter(DimWarehouse.is_current == True).all()
        }
        self.wh_sk_to_id: Dict[int, str] = {sk: wid for wid, (sk, _) in self.wh_info.items()}

        self.time_sk_to_period: Dict[int, int] = {
            t.time_period_sk: t.time_period for t in self.db.query(DimTime).all()
        }

        # TC (hằng số toàn cục)
        tc_param = self.db.query(DDSModelParameters).filter(
            DDSModelParameters.param_name == "TC"
        ).first()
        self.TC: float = float(tc_param.param_value) if tc_param else TC_DEFAULT

        # LT_PLT[(from,to)] và distance[(from,to)] từ FACT_PLT_INPUT
        self.LT_PLT: Dict[Tuple[str, str], int] = {}
        self.dist: Dict[Tuple[str, str], float] = {}
        for row in self.db.query(FactPltInput).all():
            frm = self.wh_sk_to_id.get(row.from_warehouse_sk)
            to = self.wh_sk_to_id.get(row.to_warehouse_sk)
            if frm and to:
                self.LT_PLT[(frm, to)] = int(row.lt_plt_weeks)
                if row.distance_km is not None:
                    self.dist[(frm, to)] = float(row.distance_km)

    def get_active_products(self) -> List[str]:
        return sorted(p.product_id for p in self.db.query(DimProduct).filter(
            DimProduct.is_current == True
        ).all())


def build_problem_from_dds(product_id: str, loader: DDSDataLoader) -> Optional[Problem]:
    """
    Build MA Problem từ DDS cho một product_id — tương đương build_problem()
    trong ma_adapter.py (CSV) nhưng đọc từ DDS. Logic mặc định/fallback bám
    sát TUYỆT ĐỐI bản CSV để bảo đảm 2 nguồn cho ra Problem giống hệt nhau.
    """
    db = loader.db
    warehouses = loader.warehouses
    periods = loader.periods

    product = db.query(DimProduct).filter(
        DimProduct.product_id == product_id, DimProduct.is_current == True
    ).first()
    if product is None:
        return None

    # --- CP (case-pack size): packing_details.csv có đúng 1 dòng/product_id
    # (verify: 2257/2257 sản phẩm không trùng lặp) → mọi dòng DDSPackingConfig
    # của cùng 1 SP đều cùng pack_multiple, lấy dòng đầu tiên khớp iloc[0] gốc.
    pack_row = db.query(DDSPackingConfig).filter(
        DDSPackingConfig.product_sk == product.product_sk
    ).first()
    if pack_row is None:
        return None
    CP = int(pack_row.pack_multiple)

    # --- Facts của sản phẩm này (1 dòng / (wh, t)) ---
    facts = db.query(FactInventorySMI).filter(
        FactInventorySMI.product_sk == product.product_sk
    ).all()
    if not facts:
        return None

    BI: Dict[str, float] = {wh: 0.0 for wh in warehouses}
    delta_I: Dict = {}
    U: Dict = {}
    L: Dict = {}
    CAP: Dict[int, float] = {}
    Co: Dict = {}
    Cs: Dict = {}
    Cb: Dict = {}
    Cp: Dict = {}

    for f in facts:
        wh = loader.wh_sk_to_id.get(f.warehouse_sk)
        t = loader.time_sk_to_period.get(f.time_period_sk)
        if wh is None or t is None:
            continue
        if wh in BI:
            # BI chỉ phụ thuộc (product, warehouse) — mọi dòng fact cùng SP+kho
            # có cùng giá trị (ETL ghi từ inventory_begin.csv, không đổi theo t).
            BI[wh] = float(f.beginning_inventory_qty)
        delta_I[(wh, t)] = float(f.delta_inventory_qty)
        U[(wh, t)] = float(f.inventory_ceiling)
        L[(wh, t)] = float(f.inventory_floor)
        CAP[t] = float(f.firm_capacity_qty)
        Co[(wh, t)] = float(f.cost_overstock) if f.cost_overstock is not None else 0.1
        Cs[(wh, t)] = float(f.cost_shortage) if f.cost_shortage is not None else 0.5
        Cb[(wh, t)] = float(f.cost_backorder) if f.cost_backorder is not None else 1500.0
        Cp[(wh, t)] = float(f.cost_penalty) if f.cost_penalty is not None else 2000.0

    if not delta_I:
        return None
    if not CAP:
        return None

    # Warehouse/period không có trong fact → dùng default (khớp ma_adapter.py)
    for wh in warehouses:
        for t in periods:
            if (wh, t) not in delta_I:
                delta_I[(wh, t)] = 0.0
                U[(wh, t)] = 1e6
                L[(wh, t)] = 0.0
            Co.setdefault((wh, t), 0.1)
            Cs.setdefault((wh, t), 0.5)
            Cb.setdefault((wh, t), 1500.0)
            Cp.setdefault((wh, t), 2000.0)

    # --- LT_OA: Dict[Wh, int] per-warehouse ---
    LT_OA: Dict[str, int] = {wh: loader.wh_info[wh][1] for wh in warehouses}

    # --- LT_PLT[(i,j)] — từ loader (đã nạp 1 lần) ---
    LT_PLT = dict(loader.LT_PLT)

    # --- PLT_periods: t <= LT_OA[wh] - 1 (per-warehouse, v6 model) ---
    PLT_periods = {
        wh: frozenset(t for t in periods if t <= LT_OA[wh] - 1)
        for wh in warehouses
    }

    # --- Distance dist[(i,j)] — từ loader ---
    dist = dict(loader.dist)

    # --- Cp_plt ---
    Cp_plt: Dict = {}
    for (i, j) in LT_PLT:
        for t in periods:
            Cp_plt[(i, j, t)] = Cp.get((j, t), 0.0)

    return Problem(
        product=product_id,
        warehouses=tuple(sorted(warehouses)),
        periods=tuple(periods),
        LT_OA=LT_OA,
        LT_PLT=LT_PLT,
        PLT_periods=PLT_periods,
        BI=BI,
        delta_I=delta_I,
        U=U,
        L=L,
        CAP=CAP,
        CP=CP,
        TC=loader.TC,
        dist=dist,
        Co=Co,
        Cs=Cs,
        Cb=Cb,
        Cp=Cp,
        Cp_plt=Cp_plt,
    )
