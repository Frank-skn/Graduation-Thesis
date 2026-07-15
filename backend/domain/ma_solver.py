"""
backend/domain/ma_solver.py
============================
MA (Memetic Algorithm = Hybrid GA-ALNS) solver wrapper for DSS.

Supports two modes:
1. solve_all()           — chạy trên bundled test data (case_1/2/3)
2. solve_from_dss_data() — chạy trên data thực từ DSS CSV files
"""
from __future__ import annotations

import json
import logging
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ensure backend/ma is importable regardless of working directory
# ---------------------------------------------------------------------------
_MA_DIR = Path(__file__).resolve().parent.parent / "ma"
if str(_MA_DIR) not in sys.path:
    sys.path.insert(0, str(_MA_DIR.parent))  # insert backend/ so "ma.*" resolves


def _import_ma():
    """Lazy import of MA modules to avoid load-time errors if numpy missing."""
    from ma.core.problem import Problem
    from ma.core.objective import ObjectiveCalculator
    from ma.core.constraints import ConstraintHandler
    from ma.core.decoder import Decoder
    from ma.ga.operators import GeneticOperators
    from ma.ga.genetic_algorithm import GeneticAlgorithm
    from ma.alns.alns_solver import ALNSSolver
    from ma.ga.milp_seed import generate_milp_seed
    return Problem, ObjectiveCalculator, ConstraintHandler, Decoder, GeneticOperators, GeneticAlgorithm, ALNSSolver, generate_milp_seed


# ---------------------------------------------------------------------------
# Test data paths
# ---------------------------------------------------------------------------
_TEST_DATA_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "hybrid_ga_alns" / "hybrid_ga_alns" / "test data"
)

AVAILABLE_CASES = ["case_1", "case_2", "case_3"]


# ---------------------------------------------------------------------------
# Build MA components (mirrors runner.py build_components)
# ---------------------------------------------------------------------------

def _build_components(problem, cfg: Dict, rng: random.Random, time_limit_s: float | None = None):
    (
        Problem, ObjectiveCalculator, ConstraintHandler, Decoder,
        GeneticOperators, GeneticAlgorithm, ALNSSolver, generate_milp_seed
    ) = _import_ma()

    ga_cfg   = cfg["ga"]
    alns_cfg = cfg["alns"]
    stop_cfg = cfg["stopping"]
    ls_cfg   = cfg.get("local_search", {})

    obj_calc   = ObjectiveCalculator(problem)
    constraint = ConstraintHandler(problem)
    decoder    = Decoder(problem, obj_calc)

    alns = ALNSSolver(
        problem        = problem,
        decoder        = decoder,
        obj_calc       = obj_calc,
        constraint     = constraint,
        n_iterations   = alns_cfg["n_iterations"],
        q_min_ratio    = alns_cfg["q_min_ratio"],
        q_max_ratio    = alns_cfg["q_max_ratio"],
        lambda_rho     = alns_cfg["lambda_rho"],
        segment_size   = alns_cfg["segment_size"],
        sa_accept_prob = alns_cfg["sa_initial_accept_prob"],
        sa_cooling     = alns_cfg["sa_cooling"],
        rng            = rng,
    )

    operators = GeneticOperators(
        problem     = problem,
        constraint  = constraint,
        p_crossover = ga_cfg["p_crossover"],
        p_mutation  = ga_cfg["p_mutation"],
        rng         = rng,
    )

    milp_seed = None
    if ga_cfg.get("milp_seed_fraction", 0) > 0:
        try:
            milp_seed = generate_milp_seed(
                problem    = problem,
                time_limit = int(ga_cfg.get("milp_time_limit", 15)),
            )
        except Exception:
            pass  # milp_seed is optional warm-start only

    ga = GeneticAlgorithm(
        problem                 = problem,
        decoder                 = decoder,
        obj_calc                = obj_calc,
        constraint              = constraint,
        operators               = operators,
        alns_solver             = alns,
        n_pop                   = ga_cfg["n_pop"],
        G_max                   = ga_cfg["G_max"],
        G_stag                  = ga_cfg["G_stag"],
        k_tournament            = ga_cfg["k_tournament"],
        delta_G                 = alns_cfg["delta_G"],
        top_k_alns              = alns_cfg["top_k_alns"],
        time_limit_s            = time_limit_s if time_limit_s is not None else stop_cfg["time_limit_seconds"],
        milp_seed               = milp_seed,
        rng                     = rng,
        # V6.1 local search params
        enable_local_search     = bool(ls_cfg.get("enabled", True)),
        local_search_top_k      = int(ls_cfg.get("top_k", 3)),
        local_search_max_trials = int(ls_cfg.get("max_trials", 100)),
        milp_seed_fraction      = float(ga_cfg.get("milp_seed_fraction", 0.35)),
        heuristic_fraction      = float(ga_cfg.get("heuristic_fraction", 0.45)),
    )

    return ga


# ---------------------------------------------------------------------------
# Convert DecodedSolution → DSS row dicts
# ---------------------------------------------------------------------------

def _solution_to_rows(
    product_id: str,
    problem,
    sol,
) -> List[Dict[str, Any]]:
    """
    Map MA DecodedSolution to the flat row-dict format DSS expects.

    DSS OptimizationResult schema fields:
        product_id, warehouse_id, box_id, time_period,
        q_case_pack, r_residual_units, net_inventory,
        backorder_qty, overstock_qty, shortage_qty, penalty_flag
    """
    rows: List[Dict[str, Any]] = []
    p = problem

    for t in p.periods:
        for wh in p.warehouses:
            inv   = sol.I.get((wh, t), 0.0)
            q_oa  = sol.Q_OA.get((wh, t), 0)
            r_oa  = sol.r_OA.get((wh, t), 0)

            u_val = p.U.get((wh, t), 1e9)
            l_val = p.L.get((wh, t), 0.0)

            overstock  = max(0.0, inv - u_val)
            backorder  = max(0.0, -inv)
            shortage   = max(0.0, l_val - inv)
            penalty    = r_oa > 0  # partial case-pack penalty flag

            # Dùng case_pack(wh, t) hỗ trợ cả CP dạng int lẫn dict (v6 model)
            cp_val  = p.case_pack(wh, t) if hasattr(p, "case_pack") else (p.CP if p.CP > 0 else 1)
            q_cases = q_oa // cp_val if cp_val > 0 else 0
            r_units = q_oa % cp_val  if cp_val > 0 else 0

            rows.append({
                "product_id"       : product_id,
                "warehouse_id"     : wh,
                "box_id"           : 1,          # no box concept in MA; default 1
                "time_period"      : t,
                "q_case_pack"      : int(q_cases),
                "r_residual_units" : int(r_units),
                "net_inventory"    : round(float(inv), 4),
                "backorder_qty"    : round(float(backorder), 4),
                "overstock_qty"    : round(float(overstock), 4),
                "shortage_qty"     : round(float(shortage), 4),
                "penalty_flag"     : bool(penalty),
            })

    return rows


def _solution_to_plt_rows(
    product_id: str,
    problem,
    sol,
) -> List[Dict[str, Any]]:
    """
    Extract PLT (Lateral Transshipment) transfers from DecodedSolution.Q_PLT.
    Only non-zero transfers are collected.

    Returns list of dicts with keys:
        product_id, from_warehouse_id, to_warehouse_id, time_period, qty
    """
    plt_rows: List[Dict[str, Any]] = []
    p = problem

    for (src, dst, t), qty in sol.Q_PLT.items():
        if qty <= 0:
            continue
        plt_rows.append({
            "product_id"        : product_id,
            "from_warehouse_id" : src,
            "to_warehouse_id"   : dst,
            "time_period"       : t,
            "qty"               : round(float(qty), 4),
        })

    return plt_rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class MASolver:
    """
    Wrapper that runs hybrid GA-ALNS on test data cases.

    Usage
    -----
    solver = MASolver(cfg_path=..., cases=["case_1", "case_2", "case_3"])
    result = solver.solve_all()
    # result["rows"]     → List[dict]  (DSS row format)
    # result["fitness"]  → float       (sum of all case fitnesses)
    # result["elapsed_s"]→ float
    # result["status"]   → "ok" | "partial" | "error"
    # result["details"]  → per-case breakdown
    """

    def __init__(
        self,
        cfg_path: Path | None = None,
        cases: List[str] | None = None,
        seed: int = 42,
        time_limit_s: float | None = None,
    ):
        self._cfg_path  = cfg_path or (_MA_DIR / "config.json")
        self._cases     = cases or AVAILABLE_CASES
        self._seed      = seed
        # Per-product wall-clock limit (seconds). None → use config value.
        self._time_limit_s = time_limit_s
        self._cfg       = json.loads(Path(self._cfg_path).read_text(encoding="utf-8"))
        # Override seed from config if present
        if "seed" in self._cfg:
            self._seed = int(self._cfg["seed"])

    # ------------------------------------------------------------------
    def solve_all(self) -> Dict[str, Any]:
        """Run MA on all configured test cases; aggregate results."""
        (Problem, *_) = _import_ma()

        all_rows: List[Dict[str, Any]] = []
        all_plt_rows: List[Dict[str, Any]] = []
        total_fitness = 0.0
        t_start       = time.perf_counter()
        details       = []
        n_ok = 0

        for case_name in self._cases:
            case_result = self._solve_case(case_name)
            details.append({"case": case_name, **case_result})

            if case_result["status"] in ("ok", "timeout"):
                all_rows.extend(case_result["rows"])
                all_plt_rows.extend(case_result.get("plt_rows", []))
                total_fitness += case_result["fitness"]
                n_ok += 1
                log.info(
                    "MA case %s done: fitness=%.2f elapsed=%.2fs",
                    case_name, case_result["fitness"], case_result["elapsed_s"],
                )
            else:
                log.warning("MA case %s failed: %s", case_name, case_result.get("error"))

        elapsed = time.perf_counter() - t_start
        n_total = len(self._cases)
        status  = "ok" if n_ok == n_total else ("partial" if n_ok > 0 else "error")

        log.info(
            "MASolver.solve_all done: %d/%d cases ok | total_fitness=%.2f | elapsed=%.2fs",
            n_ok, n_total, total_fitness, elapsed,
        )

        return {
            "rows"      : all_rows,
            "plt_rows"  : all_plt_rows,
            "fitness"   : total_fitness,
            "elapsed_s" : round(elapsed, 3),
            "status"    : status,
            "details"   : details,
        }

    # Nguồn dữ liệu mặc định cho solve_from_dss_data(): "dds" (kho dữ liệu
    # chiều, khớp kiến trúc Chương 5 luận văn — "DDS phục vụ trực tiếp tối
    # ưu hóa") hoặc "csv" (đọc thẳng file CSV, dùng làm lưới an toàn/rollback
    # tức thời nếu phát hiện vấn đề — không cần sửa code, chỉ đổi hằng số này).
    DEFAULT_DATA_SOURCE = "dds"

    # ------------------------------------------------------------------
    def solve_from_dss_data(
        self,
        data_dir: str,
        product_ids: List[str] | None = None,
        scenario_overrides: Dict[str, float] | None = None,
        data_source: str | None = None,
    ) -> Dict[str, Any]:
        """
        Chạy MA trên data thực của DSS.

        Parameters
        ----------
        data_dir           : đường dẫn đến folder chứa CSV files (vẫn cần cho
                             nhánh "csv", và để mở SQLite session dds.db cùng cấp)
        product_ids        : danh sách product cần chạy (None = tất cả)
        scenario_overrides : dict factor What-if/Sensitivity, ví dụ {"DI": 1.2}.
                             Áp lên INPUT của Problem (delta_I, CAP, cost...),
                             KHÔNG đụng thuật toán GA/ALNS.
        data_source         : "dds" (mặc định) hoặc "csv". Chỉ đổi NGUỒN đọc
                             input — build_problem_from_dds() đã verify khớp
                             tuyệt đối 943/943 sản phẩm với build_problem() (CSV),
                             không ảnh hưởng GA/ALNS/decoder/objective.
        """
        source = data_source or self.DEFAULT_DATA_SOURCE

        if source == "dds":
            from backend.core.database import SessionLocalDDS
            from backend.domain.dds_adapter import DDSDataLoader, build_problem_from_dds

            print("[MA] Loading DDS data...", flush=True)
            dds_session = SessionLocalDDS()
            loader = DDSDataLoader(dds_session)
            build_fn = build_problem_from_dds
        else:
            from backend.domain.ma_adapter import CSVDataLoader, build_problem

            print("[MA] Loading CSV data...", flush=True)
            dds_session = None
            loader = CSVDataLoader(data_dir)
            build_fn = build_problem

        from backend.domain.ma_adapter import apply_overrides_to_problem

        all_pids = product_ids or loader.get_active_products()

        all_rows: List[Dict[str, Any]] = []
        all_plt_rows: List[Dict[str, Any]] = []
        total_fitness = 0.0
        t_start       = time.perf_counter()
        details       = []
        n_ok = 0

        print(f"[MA] {len(all_pids)} products to solve", flush=True)

        for pid in all_pids:
            t0 = time.perf_counter()
            try:
                print(f"[MA] Solving {pid}...", flush=True)
                problem = build_fn(pid, loader)
                if problem is None:
                    print(f"[MA] Skipping {pid}: insufficient data", flush=True)
                    details.append({"product": pid, "status": "skipped"})
                    continue

                # Apply What-if / Sensitivity scaling to the Problem INPUT only
                if scenario_overrides:
                    problem = apply_overrides_to_problem(problem, scenario_overrides)

                rng = random.Random(self._seed)
                ga  = _build_components(problem, self._cfg, rng, time_limit_s=self._time_limit_s)
                _, sol = ga.run()
                elapsed = time.perf_counter() - t0

                rows = _solution_to_rows(pid, problem, sol)
                plt_rows = _solution_to_plt_rows(pid, problem, sol)
                all_rows.extend(rows)
                all_plt_rows.extend(plt_rows)
                total_fitness += float(sol.fitness)
                n_ok += 1

                log.info(
                    "  [%d/%d] %s: fitness=%.2f elapsed=%.2fs plt_transfers=%d",
                    n_ok, len(all_pids), pid, sol.fitness, elapsed, len(plt_rows),
                )
                details.append({
                    "product"  : pid,
                    "status"   : "ok",
                    "fitness"  : float(sol.fitness),
                    "elapsed_s": round(elapsed, 3),
                })

            except Exception as exc:
                elapsed = time.perf_counter() - t0
                log.error("  %s failed after %.1fs: %s", pid, elapsed, exc, exc_info=True)
                details.append({"product": pid, "status": "error", "error": str(exc)})

        elapsed_total = time.perf_counter() - t_start
        n_total = len(all_pids)
        status  = "ok" if n_ok == n_total else ("partial" if n_ok > 0 else "error")

        log.info(
            "MASolver.solve_from_dss_data done: %d/%d ok | fitness=%.2f | elapsed=%.1fs",
            n_ok, n_total, total_fitness, elapsed_total,
        )

        if dds_session is not None:
            dds_session.close()

        return {
            "rows"      : all_rows,
            "plt_rows"  : all_plt_rows,
            "fitness"   : total_fitness,
            "elapsed_s" : round(elapsed_total, 3),
            "status"    : status,
            "details"   : details,
        }

    # ------------------------------------------------------------------
    def _solve_case(self, case_name: str) -> Dict[str, Any]:
        """Run MA on a single test case. Returns result dict."""
        params_path = _TEST_DATA_DIR / case_name / "input" / "parameters.json"

        if not params_path.exists():
            return {
                "status"   : "error",
                "rows"     : [],
                "fitness"  : 0.0,
                "elapsed_s": 0.0,
                "error"    : f"parameters.json not found: {params_path}",
            }

        t0 = time.perf_counter()
        try:
            (
                Problem, ObjectiveCalculator, ConstraintHandler, Decoder,
                GeneticOperators, GeneticAlgorithm, ALNSSolver, generate_milp_seed
            ) = _import_ma()

            problem  = Problem.from_json(params_path)
            rng      = random.Random(self._seed)
            ga       = _build_components(problem, self._cfg, rng, time_limit_s=self._time_limit_s)
            _, sol   = ga.run()
            elapsed  = time.perf_counter() - t0

            rows = _solution_to_rows(
                product_id = problem.product,
                problem    = problem,
                sol        = sol,
            )
            plt_rows = _solution_to_plt_rows(
                product_id = problem.product,
                problem    = problem,
                sol        = sol,
            )

            return {
                "status"   : "ok",
                "rows"     : rows,
                "plt_rows" : plt_rows,
                "fitness"  : float(sol.fitness),
                "elapsed_s": round(elapsed, 3),
            }

        except Exception as exc:
            elapsed = time.perf_counter() - t0
            log.error("MA case %s error after %.1fs: %s", case_name, elapsed, exc, exc_info=True)
            return {
                "status"   : "error",
                "rows"     : [],
                "fitness"  : 0.0,
                "elapsed_s": round(elapsed, 3),
                "error"    : str(exc),
            }
