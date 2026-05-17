"""
model/runner.py
===============
Entry point: load config + test-data, build all components via DI,
run Hybrid GA-ALNS, and produce structured output.

Usage:
    python runner.py --case "test data/case_1"
    python runner.py --case "test data/case_1" --config model/config.json
    python runner.py --all                         # run all cases
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt= "%H:%M:%S",
)
log = logging.getLogger("runner")

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
from model.core.problem      import Problem
from model.core.objective    import ObjectiveCalculator
from model.core.constraints  import ConstraintHandler
from model.core.decoder      import Decoder
from model.ga.operators      import GeneticOperators
from model.ga.genetic_algorithm import GeneticAlgorithm
from model.ga.milp_seed      import generate_milp_seed
from model.alns.alns_solver  import ALNSSolver


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(config_path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(config_path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Component factory (Dependency Inversion)
# ---------------------------------------------------------------------------

def build_components(
    problem: Problem,
    cfg    : Dict[str, Any],
    rng    : random.Random,
) -> Tuple[GeneticAlgorithm, ALNSSolver]:
    """Wire all components together following Dependency Injection."""
    ga_cfg   = cfg["ga"]
    alns_cfg = cfg["alns"]
    stop_cfg = cfg["stopping"]

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

    # --- MILP warm start ---
    milp_seed = None
    if ga_cfg.get("milp_seed_fraction", 0) > 0:
        log.info("Generating MILP warm-start seed...")
        milp_seed = generate_milp_seed(
            problem    = problem,
            time_limit = ga_cfg.get("milp_time_limit", 15),
        )
        if milp_seed:
            log.info("MILP seed obtained.")
        else:
            log.warning("MILP seed not available; using heuristic init only.")

    def _log_cb(gen: int, best_f: float) -> None:
        if gen % 20 == 0:
            log.info("  Gen %4d | best fitness = %.4f", gen, best_f)

    ga = GeneticAlgorithm(
        problem      = problem,
        decoder      = decoder,
        obj_calc     = obj_calc,
        constraint   = constraint,
        operators    = operators,
        alns_solver  = alns,
        n_pop        = ga_cfg["n_pop"],
        G_max        = ga_cfg["G_max"],
        G_stag       = ga_cfg["G_stag"],
        k_tournament = ga_cfg["k_tournament"],
        delta_G      = alns_cfg["delta_G"],
        top_k_alns   = alns_cfg["top_k_alns"],
        time_limit_s = stop_cfg["time_limit_seconds"],
        milp_seed    = milp_seed,
        rng          = rng,
        log_callback = _log_cb,
    )

    return ga, alns


# ---------------------------------------------------------------------------
# Output serialisation
# ---------------------------------------------------------------------------

def build_output(problem: Problem, sol, elapsed: float) -> Dict[str, Any]:
    """Convert DecodedSolution → structured output dict."""
    p = problem

    schedule_rows: List[Dict] = []
    cost_rows    : List[Dict] = []
    total_cost    = 0.0

    for t in p.periods:
        for wh in p.warehouses:
            inv        = sol.I.get((wh, t), 0.0)
            q_oa       = sol.Q_OA.get((wh, t), 0)
            lt_oa      = p.LT_OA
            q_received = sol.Q_OA.get((wh, t - lt_oa), 0) if (t - lt_oa) in p.periods else 0

            plt_in  = sum(
                sol.Q_PLT.get((src, wh, t2), 0.0)
                for src in p.warehouses if src != wh
                for t2 in p.periods
                if t2 == t - p.LT_PLT.get((src, wh), 0)
            )
            plt_out = sum(
                sol.Q_PLT.get((wh, dst, t), 0.0)
                for dst in p.warehouses if dst != wh
            )
            plt_detail_parts = []
            for dst in p.warehouses:
                if dst == wh:
                    continue
                q_out = sol.Q_PLT.get((wh, dst, t), 0.0)
                if q_out > 0:
                    plt_detail_parts.append(f"{wh}→{dst}:{q_out:.0f}")

            u_val = p.U.get((wh, t), 1e9)
            l_val = p.L.get((wh, t), 0.0)
            Co_   = p.Co.get((wh, t), 0.0) * max(inv - u_val, 0.0)
            Cs_   = p.Cs.get((wh, t), 0.0) * max(l_val - inv, 0.0)
            Cb_   = p.Cb.get((wh, t), 0.0) * max(-inv, 0.0)
            r_val = sol.r_OA.get((wh, t), 0)
            Cp_   = p.Cp.get((wh, t), 0.0) if r_val > 0 else 0.0
            tc_   = 0.0  # transport computed below

            schedule_rows.append({
                "week"         : t,
                "warehouse"    : wh,
                "inv_begin"    : round(sol.I.get((wh, t - 1), p.BI.get(wh, 0.0)) if t > p.periods[0] else p.BI.get(wh, 0.0), 2),
                "Q_OA_allocated": q_oa,
                "Q_OA_received": q_received,
                "PLT_in"       : round(plt_in, 2),
                "PLT_out"      : round(plt_out, 2),
                "delta_I"      : p.delta_I.get((wh, t), 0.0),
                "inventory_end": round(inv, 2),
                "surplus_E"    : round(max(inv - l_val, 0.0), 2),
                "backorder"    : round(max(-inv, 0.0), 2),
                "shortage"     : round(max(l_val - inv, 0.0), 2),
                "overstock"    : round(max(inv - u_val, 0.0), 2),
                "PLT_detail"   : " | ".join(plt_detail_parts),
            })

        # Transport cost per period (across all PLT in that period)
        for (i, j, t2), q_plt in sol.Q_PLT.items():
            if t2 != t or q_plt <= 0:
                continue
            d_ij = p.dist.get((i, j), 0.0)
            tc_  += d_ij * p.TC

    # Cost rows per wh per period
    grand = {
        "overstock": 0.0, "shortage": 0.0, "backorder": 0.0,
        "penalty_OA": 0.0, "PLT_penalty": 0.0, "transport": 0.0, "total": 0.0
    }
    for t in p.periods:
        for wh in p.warehouses:
            inv   = sol.I.get((wh, t), 0.0)
            u_val = p.U.get((wh, t), 1e9)
            l_val = p.L.get((wh, t), 0.0)
            Co_   = p.Co.get((wh, t), 0.0) * max(inv - u_val, 0.0)
            Cs_   = p.Cs.get((wh, t), 0.0) * max(l_val - inv, 0.0)
            Cb_   = p.Cb.get((wh, t), 0.0) * max(-inv, 0.0)
            r_val = sol.r_OA.get((wh, t), 0)
            Cp_   = p.Cp.get((wh, t), 0.0) if r_val > 0 else 0.0

            tc_row = 0.0
            for (i, j, t2), q_plt in sol.Q_PLT.items():
                if t2 != t or j != wh or q_plt <= 0:
                    continue
                tc_row += p.dist.get((i, j), 0.0) * p.TC

            row_total = Co_ + Cs_ + Cb_ + Cp_ + tc_row
            total_cost += row_total

            grand["overstock"]   += Co_
            grand["shortage"]    += Cs_
            grand["backorder"]   += Cb_
            grand["penalty_OA"]  += Cp_
            grand["transport"]   += tc_row
            grand["total"]       += row_total

            cost_rows.append({
                "week"             : t,
                "warehouse"        : wh,
                "overstock_cost"   : round(Co_, 4),
                "shortage_cost"    : round(Cs_, 4),
                "backorder_cost"   : round(Cb_, 4),
                "penalty_OA_cost"  : round(Cp_, 4),
                "PLT_penalty_cost" : 0.0,
                "transport_cost"   : round(tc_row, 4),
                "total_cost"       : round(row_total, 4),
            })

    return {
        "meta": {
            "product"       : problem.product,
            "warehouses"    : list(problem.warehouses),
            "periods"       : list(problem.periods),
            "fitness"       : round(sol.fitness, 4),
            "elapsed_s"     : round(elapsed, 2),
        },
        "schedule": schedule_rows,
        "costs"   : cost_rows,
        "summary" : {
            "total_overstock_cost"   : round(grand["overstock"],   4),
            "total_shortage_cost"    : round(grand["shortage"],    4),
            "total_backorder_cost"   : round(grand["backorder"],   4),
            "total_penalty_OA_cost"  : round(grand["penalty_OA"], 4),
            "total_transport_cost"   : round(grand["transport"],   4),
            "grand_total_cost"       : round(grand["total"],       4),
        },
    }


# ---------------------------------------------------------------------------
# Save outputs
# ---------------------------------------------------------------------------

def save_outputs(output_dir: Path, result: Dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON summary
    json_path = output_dir / "results.json"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("  Saved %s", json_path)

    # Schedule CSV
    sched_path = output_dir / "schedule.csv"
    if result["schedule"]:
        with sched_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=result["schedule"][0].keys())
            w.writeheader()
            w.writerows(result["schedule"])
        log.info("  Saved %s", sched_path)

    # Cost CSV
    cost_path = output_dir / "costs.csv"
    if result["costs"]:
        with cost_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=result["costs"][0].keys())
            w.writeheader()
            w.writerows(result["costs"])
            # Summary row
            s = result["summary"]
            w.writerow({
                "week": "TOTAL", "warehouse": "ALL",
                "overstock_cost"   : s["total_overstock_cost"],
                "shortage_cost"    : s["total_shortage_cost"],
                "backorder_cost"   : s["total_backorder_cost"],
                "penalty_OA_cost"  : s["total_penalty_OA_cost"],
                "PLT_penalty_cost" : 0.0,
                "transport_cost"   : s["total_transport_cost"],
                "total_cost"       : s["grand_total_cost"],
            })
        log.info("  Saved %s", cost_path)


# ---------------------------------------------------------------------------
# Run one case
# ---------------------------------------------------------------------------

def run_case(case_dir: Path, config_path: Path) -> None:
    cfg     = load_config(config_path)
    seed    = cfg.get("seed", 42)
    rng     = random.Random(seed)

    input_dir  = case_dir / "input"
    output_dir = case_dir / "output"
    json_file  = input_dir / "parameters.json"

    if not json_file.exists():
        log.error("parameters.json not found in %s", input_dir)
        return

    log.info("=" * 60)
    log.info("Case: %s", case_dir.name)
    log.info("=" * 60)

    problem = Problem.from_json(json_file)
    log.info(
        "Problem: %s | %d warehouses | %d periods | CAP=[%s]",
        problem.product,
        problem.n_wh,
        problem.n_periods,
        ",".join(str(int(problem.CAP[t])) for t in problem.periods),
    )

    ga, alns = build_components(problem, cfg, rng)

    t0 = time.perf_counter()
    best_chrom, best_sol = ga.run()
    elapsed = time.perf_counter() - t0

    log.info(
        "Done: fitness=%.4f | elapsed=%.1fs",
        best_sol.fitness,
        elapsed,
    )

    result = build_output(problem, best_sol, elapsed)
    save_outputs(output_dir, result)

    # Pretty summary
    s = result["summary"]
    log.info("SUMMARY:")
    log.info("  Overstock cost   : %12.2f", s["total_overstock_cost"])
    log.info("  Shortage cost    : %12.2f", s["total_shortage_cost"])
    log.info("  Backorder cost   : %12.2f", s["total_backorder_cost"])
    log.info("  Penalty OA cost  : %12.2f", s["total_penalty_OA_cost"])
    log.info("  Transport cost   : %12.2f", s["total_transport_cost"])
    log.info("  GRAND TOTAL      : %12.2f", s["grand_total_cost"])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hybrid GA-ALNS solver for multi-warehouse allocation."
    )
    parser.add_argument("--case",   type=str, help="Path to a single test-case dir")
    parser.add_argument("--all",    action="store_true", help="Run all cases in 'test data/'")
    parser.add_argument(
        "--config", type=str,
        default=str(Path(__file__).parent / "model" / "config.json"),
        help="Path to config.json",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        log.error("Config not found: %s", config_path)
        sys.exit(1)

    if args.all:
        # Discover all case_* dirs under 'test data/'
        test_data_dir = Path(__file__).parent / "test data"
        cases = sorted(d for d in test_data_dir.iterdir() if d.is_dir() and d.name.startswith("case"))
        for case_dir in cases:
            run_case(case_dir, config_path)
    elif args.case:
        run_case(Path(args.case), config_path)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
