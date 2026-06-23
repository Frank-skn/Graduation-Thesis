"""
CSV-based implementation of IOptimizationDataRepository.

Reads optimization input data directly from CSV files in the data/
directory. This eliminates any dependency on PostgreSQL for DDS data.

CSV files expected (all in data_dir/):
  - product.csv         : product_id, item_class, ...
  - warehouse.csv       : warehouse_id, market_code, ...
  - time_period.csv     : time_period, start_date, ...
  - inventory_begin.csv : product_id, warehouse_id, beginning_inventory
  - inventory_flow.csv  : product_id, warehouse_id, time_period,
                          inventory_fluctuation, inventory_ceiling,
                          inventory_floor
  - unit_cost.csv       : product_id, warehouse_id, time_period,
                          overstock_cost, shortage_cost, backlog_cost,
                          penalty_cost
  - packing_details.csv : product_id, box_id, pack_multiple
  - box_shipment.csv    : packing_details_id, warehouse_id, is_active
  - vendor_capacity.csv : product_id, time_period, capacity
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

import pandas as pd

from backend.data_access.interfaces import IOptimizationDataRepository
from backend.schemas.optimization import OptimizationInput


class CsvOptimizationDataRepository(IOptimizationDataRepository):
    """Repository that builds OptimizationInput from CSV files."""

    def __init__(self, data_dir: str) -> None:
        self._dir = Path(data_dir)
        self._load()

    # ---------------------------------------------------------------- #
    #  Internal data load                                               #
    # ---------------------------------------------------------------- #

    def _load(self) -> None:
        """Load all relevant CSV files into pandas DataFrames."""
        self._products = pd.read_csv(self._dir / "product.csv", dtype=str)
        self._warehouses = pd.read_csv(self._dir / "warehouse.csv", dtype=str)
        self._periods = pd.read_csv(self._dir / "time_period.csv")

        self._inv_begin = pd.read_csv(
            self._dir / "inventory_begin.csv", dtype={"product_id": str, "warehouse_id": str}
        )
        self._inv_flow = pd.read_csv(
            self._dir / "inventory_flow.csv", dtype={"product_id": str, "warehouse_id": str}
        )
        self._unit_cost = pd.read_csv(
            self._dir / "unit_cost.csv", dtype={"product_id": str, "warehouse_id": str}
        )
        self._packing = pd.read_csv(
            self._dir / "packing_details.csv", dtype={"product_id": str}
        )
        self._box_shipment = pd.read_csv(
            self._dir / "box_shipment.csv", dtype={"warehouse_id": str}
        )
        self._capacity = pd.read_csv(
            self._dir / "vendor_capacity.csv", dtype={"product_id": str}
        )

    # ---------------------------------------------------------------- #
    #  IOptimizationDataRepository implementation                       #
    # ---------------------------------------------------------------- #

    def get_products(self) -> List[str]:
        # Only return products that have actual inventory flow data (active products)
        active = self._inv_flow["product_id"].str.strip().unique().tolist()
        return sorted(active)

    def get_warehouses(self) -> List[str]:
        return self._warehouses["warehouse_id"].tolist()

    def get_time_periods(self) -> List[int]:
        return sorted(self._periods["time_period"].astype(int).tolist())

    def get_actual_combination_counts(self) -> dict:
        """
        Return actual distinct combination counts for each parameter group.

        These are the *real* domains of the optimization problem derived
        from the CSV files, not the theoretical Cartesian products:
          - ij_flow   : distinct (i,j) from inventory_flow  → denominator for BI
          - ijt_flow  : distinct (i,j,t) from inventory_flow → denominator for U/L/DI/Cb/Co/Cs/Cp
          - ij_theor  : |I|×|J| theoretical                 → denominator for CP
          - it        : |I|×|T| = len(CAP)                  → denominator for CAP
        """
        ij_flow = (
            self._inv_flow
            .groupby(["product_id", "warehouse_id"])
            .ngroups
        )
        ijt_flow = (
            self._inv_flow
            .groupby(["product_id", "warehouse_id", "time_period"])
            .ngroups
        )
        ij_theor = len(self._products) * len(self._warehouses)
        it = len(self._products) * len(self._periods)
        return {
            "ij_flow":  ij_flow,
            "ijt_flow": ijt_flow,
            "ij_theor": ij_theor,
            "it":       it,
        }

    def get_optimization_input(self) -> OptimizationInput:
        I = self.get_products()
        J = self.get_warehouses()
        T = self.get_time_periods()

        BI: dict = {}
        CP: dict = {}
        U: dict = {}
        L: dict = {}
        DI: dict = {}
        CAP: dict = {}
        Cb: dict = {}
        Co: dict = {}
        Cs: dict = {}
        Cp: dict = {}

        # ── Beginning Inventory: BI[(i, j)] ─────────────────────────
        for _, row in self._inv_begin.iterrows():
            key = (str(row["product_id"]), str(row["warehouse_id"]))
            BI[key] = float(row["beginning_inventory"])

        # ── Inventory flow: U, L, DI all keyed (i, j, t) ────────────
        for _, row in self._inv_flow.iterrows():
            key = (
                str(row["product_id"]),
                str(row["warehouse_id"]),
                int(row["time_period"]),
            )
            U[key] = float(row["inventory_ceiling"])
            L[key] = float(row["inventory_floor"])
            DI[key] = float(row["inventory_fluctuation"])

        # ── Vendor capacity: CAP[(i, t)] ─────────────────────────────
        for _, row in self._capacity.iterrows():
            key = (str(row["product_id"]), int(row["time_period"]))
            CAP[key] = float(row["capacity"])

        # ── Unit costs: Cb, Co, Cs, Cp keyed (i, j, t) ──────────────
        for _, row in self._unit_cost.iterrows():
            key = (
                str(row["product_id"]),
                str(row["warehouse_id"]),
                int(row["time_period"]),
            )
            Co[key] = float(row["overstock_cost"])
            Cs[key] = float(row["shortage_cost"])
            Cb[key] = float(row["backlog_cost"])
            Cp[key] = float(row["penalty_cost"])

        # ── Case pack: CP[(i, j)] ────────────────────────────────────
        # packing_details.csv row position (1-based) == packing_details_id
        # box_shipment.csv links packing_details_id → warehouse_id
        packing_indexed = self._packing.reset_index(drop=True)
        packing_indexed.index = packing_indexed.index + 1  # 1-based index

        # Build product_id lookup by packing row index
        pd_id_to_product: dict[int, tuple] = {}
        for idx, row in packing_indexed.iterrows():
            pd_id_to_product[int(idx)] = (
                str(row["product_id"]),
                int(row["pack_multiple"]),
            )

        # Filter active shipments only
        active_ship = self._box_shipment[
            self._box_shipment["is_active"].astype(str).str.lower() == "true"
        ]

        for _, row in active_ship.iterrows():
            pd_id = int(row["packing_details_id"])
            wh_id = str(row["warehouse_id"])
            if pd_id in pd_id_to_product:
                prod_id, pack_mult = pd_id_to_product[pd_id]
                CP[(prod_id, wh_id)] = pack_mult

        # ── HV: large constant for linearisation ─────────────────────
        HV: float = 9999.0

        return OptimizationInput(
            I=I, J=J, T=T,
            BI=BI, CP=CP, U=U, L=L, DI=DI, CAP=CAP,
            Cb=Cb, Co=Co, Cs=Cs, Cp=Cp,
            HV=HV,
        )


# -------------------------------------------------------------------- #
#  Module-level cached singleton                                        #
# -------------------------------------------------------------------- #

_instance: CsvOptimizationDataRepository | None = None


def get_csv_repo(data_dir: str) -> CsvOptimizationDataRepository:
    """Return (or create) the cached CSV repository."""
    global _instance
    if _instance is None:
        _instance = CsvOptimizationDataRepository(data_dir)
    return _instance
