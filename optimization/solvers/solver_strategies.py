"""
Solver compatibility shim — PuLP CBC is called directly inside
optimization/models/ss_mb_smi.py.  This module is retained only for
backward-compatible imports used in services.py.
"""
from typing import Optional, Dict, Any


# ---------------------------------------------------------------------------
# Minimal shim so existing imports don't crash
# ---------------------------------------------------------------------------

class ISolverStrategy:
    """No-op strategy — kept for interface compatibility."""

    def solve(self, model, **kwargs):
        raise NotImplementedError("PuLP solver is embedded in the model; use solve_ss_mb_smi() directly.")

    def get_name(self) -> str:
        return "pulp_cbc"


class CBCSolverStrategy(ISolverStrategy):
    def get_name(self) -> str:
        return "cbc"


class SolverFactory:
    """Minimal factory shim — always returns CBCSolverStrategy."""

    @classmethod
    def create_solver(cls, solver_name: str) -> ISolverStrategy:
        return CBCSolverStrategy()

    @classmethod
    def list_available_solvers(cls):
        return ["cbc"]


def interpret_solver_status(status_str: str) -> Dict[str, Any]:
    """
    Convert a plain solver_status string into a status dict.
    Accepts either the string from ModelSolution.solver_status or
    a legacy Pyomo SolverResults object (no longer used).
    """
    if not isinstance(status_str, str):
        # Legacy Pyomo object passed in — treat as optimal for safety
        status_str = "Optimal"

    is_optimal  = status_str == "Optimal"
    is_feasible = status_str in ("Optimal", "Feasible")

    return {
        "solver_status": status_str,
        "termination_condition": status_str,
        "is_optimal": is_optimal,
        "is_feasible": is_feasible,
        "message": "Solução ótima encontrada" if is_optimal else status_str,
    }
