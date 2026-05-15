"""
backend/domain/ma_adapter.py
=============================
Convert DSS CSV data → MA Problem object cho từng product.

Mapping warehouse order (theo thứ tự WH01→WH06):
    WH01 → MI, WH02 → OH, WH03 → IN, WH04 → IL, WH05 → KY, WH06 → MO
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

# Ensure backend/ma importable
_MA_DIR = Path(__file__).resolve().parent.parent / "ma"
if str(_MA_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_MA_DIR.parent))

from ma.core.problem import Problem

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TC_DEFAULT = 1.2  # 40ft Dry container (container_pricing.csv row 2)
LT_OA_DEFAULT = 8  # week_lead_time từ oa_lead_time.csv (đồng nhất = 8)

# Mapping WH01-WH06 → State code trong FGPs_distance.csv
WH_TO_STATE = {
    "WH01": "MI",
    "WH02": "OH",
    "WH03": "IN",
    "WH04": "IL",
    "WH05": "KY",
    "WH06": "MO",
}


# ---------------------------------------------------------------------------
# Data loader (load 1 lần, cache lại)
# ---------------------------------------------------------------------------

class CSVDataLoader:
    """Load và cache tất cả CSV files cần thiết cho MA adapter."""

    def __init__(self, data_dir: str | Path):
        self._dir = Path(data_dir)
        self._load()

    def _load(self):
        self.warehouses: List[str] = (
            pd.read_csv(self._dir / "warehouse.csv", dtype=str)["warehouse_id"].tolist()
        )
        self.periods: List[int] = sorted(
            pd.read_csv(self._dir / "time_period.csv")["time_period"].astype(int).tolist()
        )
        self.inv_begin = pd.read_csv(
            self._dir / "inventory_begin.csv",
            dtype={"product_id": str, "warehouse_id": str},
        )
        self.inv_flow = pd.read_csv(
            self._dir / "inventory_flow.csv",
            dtype={"product_id": str, "warehouse_id": str},
        )
        self.capacity = pd.read_csv(
            self._dir / "vendor_capacity.csv",
            dtype={"product_id": str},
        )
        self.unit_cost = pd.read_csv(
            self._dir / "unit_cost.csv",
            dtype={"product_id": str, "warehouse_id": str},
        )
        self.packing = pd.read_csv(
            self._dir / "packing_details.csv",
            dtype={"product_id": str},
        )
        self.plt_lead = pd.read_csv(self._dir / "plt_lead_time.csv")
        self.distance_matrix = pd.read_csv(
            self._dir / "FGPs_distance.csv", index_col="State"
        )

    def get_active_products(self) -> List[str]:
        return sorted(self.inv_flow["product_id"].str.strip().unique().tolist())


# ---------------------------------------------------------------------------
# Core adapter function
# ---------------------------------------------------------------------------

def build_problem(product_id: str, loader: CSVDataLoader) -> Optional[Problem]:
    """
    Build một MA Problem từ DSS CSV data cho một product_id.
    Trả về None nếu product không có đủ dữ liệu để chạy.
    """
    warehouses = loader.warehouses
    periods    = loader.periods

    # --- CP (case-pack size) ---
    cp_row = loader.packing[loader.packing["product_id"] == product_id]
    if cp_row.empty:
        return None
    CP = int(cp_row.iloc[0]["pack_multiple"])

    # --- Beginning Inventory BI[wh] ---
    bi_df = loader.inv_begin[loader.inv_begin["product_id"] == product_id]
    BI: Dict[str, float] = {wh: 0.0 for wh in warehouses}
    for _, row in bi_df.iterrows():
        wh = str(row["warehouse_id"])
        if wh in BI:
            BI[wh] = float(row["beginning_inventory"])

    # --- Inventory flow: delta_I, U, L ---
    flow_df = loader.inv_flow[loader.inv_flow["product_id"] == product_id]
    if flow_df.empty:
        return None

    delta_I: Dict = {}
    U: Dict = {}
    L: Dict = {}
    for _, row in flow_df.iterrows():
        wh = str(row["warehouse_id"])
        t  = int(row["time_period"])
        delta_I[(wh, t)] = float(row["inventory_fluctuation"])
        U[(wh, t)]       = float(row["inventory_ceiling"])
        L[(wh, t)]       = float(row["inventory_floor"])

    # Warehouse/period không có trong flow → dùng default
    for wh in warehouses:
        for t in periods:
            if (wh, t) not in delta_I:
                delta_I[(wh, t)] = 0.0
                U[(wh, t)]       = 1e6
                L[(wh, t)]       = 0.0

    # --- CAP[t] ---
    cap_df = loader.capacity[loader.capacity["product_id"] == product_id]
    if cap_df.empty:
        return None
    CAP: Dict[int, float] = {}
    for _, row in cap_df.iterrows():
        CAP[int(row["time_period"])] = float(row["capacity"])

    # --- Costs: Co, Cs, Cb, Cp ---
    cost_df = loader.unit_cost[loader.unit_cost["product_id"] == product_id]
    Co: Dict = {}
    Cs: Dict = {}
    Cb: Dict = {}
    Cp: Dict = {}
    for _, row in cost_df.iterrows():
        wh = str(row["warehouse_id"])
        t  = int(row["time_period"])
        Co[(wh, t)] = float(row["overstock_cost"])
        Cs[(wh, t)] = float(row["shortage_cost"])
        Cb[(wh, t)] = float(row["backlog_cost"])
        Cp[(wh, t)] = float(row["penalty_cost"])

    # Default costs nếu thiếu
    for wh in warehouses:
        for t in periods:
            Co.setdefault((wh, t), 0.1)
            Cs.setdefault((wh, t), 0.5)
            Cb.setdefault((wh, t), 1500.0)
            Cp.setdefault((wh, t), 2000.0)

    # --- LT_OA ---
    LT_OA = LT_OA_DEFAULT

    # --- LT_PLT[(i,j)] ---
    # plt_lead_time.csv dùng số (1-6), map sang WHxx
    wh_num = {str(i+1): f"WH0{i+1}" for i in range(6)}
    LT_PLT: Dict = {}
    for _, row in loader.plt_lead.iterrows():
        frm = wh_num.get(str(int(row["from_warehouse_id"])))
        to  = wh_num.get(str(int(row["to_warehouse_id"])))
        if frm and to:
            LT_PLT[(frm, to)] = int(row["lead_time_weeks"])

    # --- PLT_periods: t ≤ LT_OA - 1 ---
    plt_cutoff = LT_OA - 1
    PLT_periods = {
        wh: frozenset(t for t in periods if t <= plt_cutoff)
        for wh in warehouses
    }

    # --- Distance dist[(i,j)] ---
    dist: Dict = {}
    dm = loader.distance_matrix
    for wh_i in warehouses:
        for wh_j in warehouses:
            if wh_i == wh_j:
                continue
            s_i = WH_TO_STATE.get(wh_i)
            s_j = WH_TO_STATE.get(wh_j)
            if s_i and s_j and s_i in dm.index and s_j in dm.columns:
                dist[(wh_i, wh_j)] = float(dm.loc[s_i, s_j])

    # --- Cp_plt ---
    Cp_plt: Dict = {}
    for (i, j) in LT_PLT:
        for t in periods:
            Cp_plt[(i, j, t)] = Cp.get((j, t), 0.0)

    return Problem(
        product     = product_id,
        warehouses  = tuple(sorted(warehouses)),
        periods     = tuple(periods),
        LT_OA       = LT_OA,
        LT_PLT      = LT_PLT,
        PLT_periods = PLT_periods,
        BI          = BI,
        delta_I     = delta_I,
        U           = U,
        L           = L,
        CAP         = CAP,
        CP          = CP,
        TC          = TC_DEFAULT,
        dist        = dist,
        Co          = Co,
        Cs          = Cs,
        Cb          = Cb,
        Cp          = Cp,
        Cp_plt      = Cp_plt,
    )
