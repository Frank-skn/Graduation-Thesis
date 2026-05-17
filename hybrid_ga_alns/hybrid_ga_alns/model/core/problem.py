"""
core/problem.py
===============
Immutable data-container representing one single-product sub-problem.

All indices use Python objects (strings for warehouses, ints for periods).
- Compatible with the multi-warehouse, multi-period math model in math_model.tex.
- See algorithsm/hybrid_ga_alns_standalone.tex for notation.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, List, Tuple


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Wh   = str            # warehouse id, e.g. "WH01"
Pd   = int            # period index, 1-based
QOAChrom = Dict[Tuple[Wh, Pd], int]   # chromosome representation


@dataclass(frozen=True)
class Problem:
    """
    Single-product sub-problem (all arrays keyed by warehouse / period).

    Attributes
    ----------
    product : str
    warehouses : tuple[str, ...]          sorted list of warehouse IDs
    periods : tuple[int, ...]             sorted 1-based period indices
    LT_OA : int                           OA lead-time (same for every warehouse)
    LT_PLT : Dict[(i,j), int]            PLT lead-time for ordered pair (i,j)
    PLT_periods : Dict[j, FrozenSet[t]]  valid PLT periods for receiving wh j
    BI  : Dict[wh, float]                beginning inventory
    delta_I : Dict[(wh,t), float]        inventory change (demand+returns)
    U   : Dict[(wh,t), float]            ceiling inventory level
    L   : Dict[(wh,t), float]            floor inventory level
    CAP : Dict[t, float]                 total allocation capacity per period
    CP  : int                            case-pack size (uniform in data)
    TC  : float                          unit transport cost coefficient
    dist : Dict[(i,j), float]            distance between warehouse pairs
    Co  : Dict[(wh,t), float]            overstock cost
    Cs  : Dict[(wh,t), float]            shortage cost
    Cb  : Dict[(wh,t), float]            backorder cost
    Cp  : Dict[(wh,t), float]            OA partial-case penalty
    Cp_plt : Dict[(i,j,t), float]        PLT partial-case penalty
    """

    product    : str
    warehouses : Tuple[Wh, ...]
    periods    : Tuple[Pd, ...]
    LT_OA      : int
    LT_PLT     : Dict[Tuple[Wh, Wh], int]
    PLT_periods: Dict[Wh, FrozenSet[Pd]]   # T_j^PLT per receiving wh
    BI         : Dict[Wh, float]
    delta_I    : Dict[Tuple[Wh, Pd], float]
    U          : Dict[Tuple[Wh, Pd], float]
    L          : Dict[Tuple[Wh, Pd], float]
    CAP        : Dict[Pd, float]
    CP         : int
    TC         : float
    dist       : Dict[Tuple[Wh, Wh], float]
    Co         : Dict[Tuple[Wh, Pd], float]
    Cs         : Dict[Tuple[Wh, Pd], float]
    Cb         : Dict[Tuple[Wh, Pd], float]
    Cp         : Dict[Tuple[Wh, Pd], float]
    Cp_plt     : Dict[Tuple[Wh, Wh, Pd], float]

    # ------------------------------------------------------------------
    # Convenience helpers (computed from primary fields)
    # ------------------------------------------------------------------
    @property
    def n_wh(self) -> int:
        return len(self.warehouses)

    @property
    def n_periods(self) -> int:
        return len(self.periods)

    def plt_valid(self, i: Wh, j: Wh, t: Pd) -> bool:
        """True iff PLT from i→j is valid at period t."""
        return (i, j) in self.LT_PLT and t in self.PLT_periods.get(j, frozenset())

    # ------------------------------------------------------------------
    # Factory method
    # ------------------------------------------------------------------
    @classmethod
    def from_json(cls, json_path: str | Path) -> "Problem":
        """
        Build a Problem from the test-data parameters.json format.

        Expected keys: meta, OA_lead, PLT_lead, CP, TC, BI, delta_I,
                       U, L, CAP, cost, distance
        """
        params = json.loads(Path(json_path).read_text(encoding="utf-8"))

        meta       = params["meta"]
        product    = meta["product"]
        warehouses = tuple(sorted(meta["warehouses"]))
        T          = sorted(range(1, meta["T"] + 1))

        LT_OA: int = int(params["OA_lead"])

        # PLT lead-times   key format "WHxx_WHyy"
        LT_PLT: Dict[Tuple[Wh, Wh], int] = {}
        for raw_key, lt in params["PLT_lead"].items():
            frm, to = raw_key.split("_", 1)
            LT_PLT[(frm, to)] = int(lt)

        # T_j^PLT = { t ∈ T : t ≤ LT_j^OA − 1 }
        # Since LT_OA is uniform: all t ≤ LT_OA - 1
        plt_cutoff = LT_OA - 1
        PLT_periods: Dict[Wh, FrozenSet[Pd]] = {
            wh: frozenset(t for t in T if t <= plt_cutoff)
            for wh in warehouses
        }

        CP: int   = int(params["CP"])
        TC: float = float(params["TC"])

        # BI
        BI: Dict[Wh, float] = {wh: float(params["BI"][wh]) for wh in warehouses}

        # delta_I  key format "WHxx_t"
        delta_I: Dict[Tuple[Wh, Pd], float] = {}
        for raw_key, val in params["delta_I"].items():
            parts  = raw_key.rsplit("_", 1)
            wh, t_ = parts[0], int(parts[1])
            delta_I[(wh, t_)] = float(val)

        def _parse_wh_t(d: dict) -> Dict[Tuple[Wh, Pd], float]:
            out: Dict[Tuple[Wh, Pd], float] = {}
            for raw_key, val in d.items():
                parts = raw_key.rsplit("_", 1)
                out[(parts[0], int(parts[1]))] = float(val)
            return out

        U = _parse_wh_t(params["U"])
        L = _parse_wh_t(params["L"])

        # CAP  key is stringified period
        CAP: Dict[Pd, float] = {int(k): float(v) for k, v in params["CAP"].items()}

        # Costs  nested: cost[wh][t][type]
        Co: Dict[Tuple[Wh, Pd], float] = {}
        Cs: Dict[Tuple[Wh, Pd], float] = {}
        Cb: Dict[Tuple[Wh, Pd], float] = {}
        Cp: Dict[Tuple[Wh, Pd], float] = {}
        for wh, periods_dict in params["cost"].items():
            for t_str, cost_dict in periods_dict.items():
                t_ = int(t_str)
                Co[(wh, t_)] = float(cost_dict.get("overstock", 0))
                Cs[(wh, t_)] = float(cost_dict.get("shortage",  0))
                Cb[(wh, t_)] = float(cost_dict.get("backorder", 0))
                Cp[(wh, t_)] = float(cost_dict.get("penalty",   0))

        # Distances  key format "WHxx_WHyy"
        dist: Dict[Tuple[Wh, Wh], float] = {}
        for raw_key, val in params["distance"].items():
            frm, to = raw_key.split("_", 1)
            dist[(frm, to)] = float(val)

        # PLT penalty (use same as OA penalty per warehouse pair, can extend)
        Cp_plt: Dict[Tuple[Wh, Wh, Pd], float] = {}
        for (i, j) in LT_PLT:
            for t_ in T:
                # Use the receiving warehouse's OA penalty as PLT penalty
                Cp_plt[(i, j, t_)] = Cp.get((j, t_), 0.0)

        return cls(
            product     = product,
            warehouses  = warehouses,
            periods     = tuple(T),
            LT_OA       = LT_OA,
            LT_PLT      = LT_PLT,
            PLT_periods = PLT_periods,
            BI          = BI,
            delta_I     = delta_I,
            U           = U,
            L           = L,
            CAP         = CAP,
            CP          = CP,
            TC          = TC,
            dist        = dist,
            Co          = Co,
            Cs          = Cs,
            Cb          = Cb,
            Cp          = Cp,
            Cp_plt      = Cp_plt,
        )
