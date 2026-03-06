"""
Benchmark SS-MB-SMI trên data thực tế.
Chạy từng item subproblem độc lập, ghi nhận thời gian và trạng thái.
Sử dụng: python benchmark_real_data.py  (từ thư mục data_test hoặc bất kỳ đâu)
"""
import time
import sys
from pathlib import Path

import pandas as pd
import pulp
import matplotlib
matplotlib.use("Agg")   # no display needed
import matplotlib.pyplot as plt
matplotlib.use("Agg")          # non-interactive backend (no display needed)
import matplotlib.pyplot as plt

DATA_DIR = Path(__file__).parent.parent / "data"
HV = 9999
TIME_LIMIT = 30  # seconds per subproblem

# ── Helpers ────────────────────────────────────────────────────────────────
def as_str(v): return str(v).strip()

def safe(v):
    x = pulp.value(v)
    return 0.0 if x is None else float(x)

def load_data():
    def read(name, dtype=None):
        df = pd.read_csv(DATA_DIR / f"{name}.csv", dtype=dtype)
        df.columns = df.columns.str.strip().str.lower()
        return df

    inv_begin = read("inventory_begin",
                     dtype={"product_id": str, "warehouse_id": str})
    inv_flow  = read("inventory_flow",
                     dtype={"product_id": str, "warehouse_id": str})
    uc        = read("unit_cost",
                     dtype={"product_id": str, "warehouse_id": str})
    pack_det  = read("packing_details", dtype={"product_id": str})
    box_ship  = read("box_shipment",    dtype={"warehouse_id": str})
    ven_cap   = read("vendor_capacity", dtype={"product_id": str})
    tp        = read("time_period")

    for df, cols in ((inv_begin, ("product_id", "warehouse_id")),
                     (inv_flow,  ("product_id", "warehouse_id")),
                     (uc,        ("product_id", "warehouse_id")),
                     (box_ship,  ("warehouse_id",))):
        for c in cols:
            df[c] = df[c].map(as_str)
    pack_det["product_id"] = pack_det["product_id"].map(as_str)

    inv_flow["time_period"] = inv_flow["time_period"].astype(int)
    uc["time_period"]       = uc["time_period"].astype(int)
    ven_cap["time_period"]  = ven_cap["time_period"].astype(int)
    tp["time_period"]       = tp["time_period"].astype(int)

    T = sorted(tp["time_period"].unique().tolist())

    # CP: (product_id, warehouse_id) → pack_multiple
    # box_shipment.packing_details_id is 1-based row position in packing_details
    pack_det = pack_det.reset_index(drop=True)
    pack_lookup = {
        idx + 1: (as_str(r.product_id), int(r.pack_multiple))
        for idx, r in pack_det.iterrows()
    }

    active_ship = box_ship
    if "is_active" in box_ship.columns:
        active_ship = box_ship[
            box_ship["is_active"].astype(str).str.lower().eq("true")
        ]
    pid_col = ("packing_details_id"
               if "packing_details_id" in box_ship.columns else "box_id")

    CP: dict[tuple, int] = {}
    for _, r in active_ship.iterrows():
        pd_id = int(getattr(r, pid_col))
        if pd_id in pack_lookup:
            ip, cpv = pack_lookup[pd_id]
            CP[(ip, as_str(r.warehouse_id))] = cpv

    BI = {
        (as_str(r.product_id), as_str(r.warehouse_id)): float(r.beginning_inventory)
        for _, r in inv_begin.iterrows()
    }
    U, L, DI = {}, {}, {}
    for _, r in inv_flow.iterrows():
        k = (as_str(r.product_id), as_str(r.warehouse_id), int(r.time_period))
        U[k]  = float(r.inventory_ceiling)
        L[k]  = float(r.inventory_floor)
        DI[k] = float(r.inventory_fluctuation)

    CAP = {
        (as_str(r.product_id), int(r.time_period)): float(r.capacity)
        for _, r in ven_cap.iterrows()
    }

    Co, Cs, Cb, Cp_cost = {}, {}, {}, {}
    for _, r in uc.iterrows():
        k = (as_str(r.product_id), as_str(r.warehouse_id), int(r.time_period))
        Co[k]      = float(r.overstock_cost)
        Cs[k]      = float(r.shortage_cost)
        Cb[k]      = float(r.backlog_cost)
        Cp_cost[k] = float(r.penalty_cost)

    # Build J_by_i
    J_by_i: dict[str, list[str]] = {}
    for (i, j, _) in DI.keys():
        J_by_i.setdefault(i, [])
        if j not in J_by_i[i]:
            J_by_i[i].append(j)

    I_list = sorted(J_by_i.keys())

    return T, I_list, J_by_i, BI, DI, U, L, CAP, CP, Co, Cs, Cb, Cp_cost


# ── Per-item solver ─────────────────────────────────────────────────────────
def solve_item(item, j_list, T, BI, DI, U, L, CAP, CP, Co, Cs, Cb, Cp_cost):
    ijt = [(item, j, t) for j in j_list for t in T]

    sub = pulp.LpProblem(f"SS_{item}", pulp.LpMinimize)

    q_v  = pulp.LpVariable.dicts("q",  ijt, lowBound=0, cat="Integer")
    r_v  = {}
    for i_, j_, t_ in ijt:
        cp = max(1, int(CP.get((i_, j_), 1)))
        r_v[(i_, j_, t_)] = pulp.LpVariable(
            f"r_{i_}_{j_}_{t_}", lowBound=0, upBound=cp - 1, cat="Integer")
    Iv   = pulp.LpVariable.dicts("I",  ijt, lowBound=None, cat="Continuous")
    bo   = pulp.LpVariable.dicts("bo", ijt, lowBound=0,    cat="Continuous")
    o_v  = pulp.LpVariable.dicts("o",  ijt, lowBound=0,    cat="Continuous")
    s_v  = pulp.LpVariable.dicts("s",  ijt, lowBound=0,    cat="Continuous")
    p_v  = pulp.LpVariable.dicts("p",  ijt, cat="Binary")

    sub += pulp.lpSum(
        Co.get(k,0)*o_v[k] + Cs.get(k,0)*s_v[k] +
        Cb.get(k,0)*bo[k]  + Cp_cost.get(k,0)*p_v[k]
        for k in ijt
    ) + 0.0 * q_v[ijt[0]]

    t0 = T[0]
    for j in j_list:
        cp = max(1, int(CP.get((item, j), 1)))
        sub += (Iv[(item, j, t0)] ==
                BI.get((item, j), 0) + DI.get((item, j, t0), 0)
                + q_v[(item, j, t0)] * cp + r_v[(item, j, t0)])
        for ki in range(1, len(T)):
            tc, tp_prev = T[ki], T[ki - 1]
            sub += (Iv[(item, j, tc)] ==
                    Iv[(item, j, tp_prev)] + DI.get((item, j, tc), 0)
                    + q_v[(item, j, tc)] * cp + r_v[(item, j, tc)])

    for t in T:
        sub += (
            pulp.lpSum(
                q_v[(item, j, t)] * max(1, int(CP.get((item, j), 1)))
                + r_v[(item, j, t)]
                for j in j_list
            ) == CAP.get((item, t), 0)
        )

    for j in j_list:
        for t in T:
            k = (item, j, t)
            sub += bo[k]  >= -Iv[k]
            sub += o_v[k] >= Iv[k] - U.get(k, HV)
            sub += s_v[k] >= L.get(k, 0) - Iv[k]
            sub += r_v[k] <= HV * p_v[k]
            sub += r_v[k] >= HV * (p_v[k] - 1) + 1

    t_start = time.perf_counter()
    sub.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=TIME_LIMIT))
    elapsed = time.perf_counter() - t_start

    status = pulp.LpStatus[sub.status]
    obj    = pulp.value(sub.objective) or 0.0

    # ── Detailed cost & allocation breakdown ───────────────────────────────
    detail = {
        "status": status, "elapsed": elapsed, "obj": obj,
        "cost_bo": 0.0, "cost_o": 0.0, "cost_s": 0.0, "cost_p": 0.0,
        # allocation behaviour counters (per (item,t) period)
        "periods": [],          # list of dicts per period t
    }

    def _v(var): return float(pulp.value(var) or 0.0)

    for t in T:
        alloc_by_wh = {}   # wh → units allocated this period
        has_residual = False
        has_bo       = False
        cap_t = CAP.get((item, t), 0)

        for j in j_list:
            k = (item, j, t)
            cp  = max(1, int(CP.get((item, j), 1)))
            qv  = _v(q_v[k])
            rv  = _v(r_v[k])
            pv  = _v(p_v[k])
            bov = _v(bo[k])
            ov  = _v(o_v[k])
            sv  = _v(s_v[k])

            detail["cost_bo"] += Cb.get(k, 0) * bov
            detail["cost_o"]  += Co.get(k, 0) * ov
            detail["cost_s"]  += Cs.get(k, 0) * sv
            detail["cost_p"]  += Cp_cost.get(k, 0) * round(pv)

            units = qv * cp + rv
            alloc_by_wh[j] = units
            if rv > 0.5:
                has_residual = True
            if bov > 0.01:
                has_bo = True

        # dominant warehouse: does any single WH get >70% of CAP?
        dominant = (max(alloc_by_wh.values()) > 0.70 * cap_t) if cap_t > 0 else False

        detail["periods"].append({
            "t": t,
            "dominant": dominant,
            "has_residual": has_residual,
            "has_bo": has_bo,
        })

    return detail


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    print("Đang tải data thực tế...")
    T, I_list, J_by_i, BI, DI, U, L, CAP, CP, Co, Cs, Cb, Cp_cost = load_data()

    n_items = len(I_list)
    print(f"Tổng số items (subproblems): {n_items:,}   |   T = {T}")
    print("Bắt đầu giải từng subproblem...\n")

    results      = []   # list of detail dicts  +  item key
    milestones   = []   # (n_solved, avg_time_s, cumulative_runtime_s)
    MILESTONE_STEP = 100
    batch_start  = time.perf_counter()

    for idx, item in enumerate(I_list, 1):
        j_list = sorted(J_by_i.get(item, []))
        if not j_list:
            continue

        det = solve_item(
            item, j_list, T,
            BI, DI, U, L, CAP, CP, Co, Cs, Cb, Cp_cost
        )
        det["item"] = item
        results.append(det)

        done = len(results)
        # Record milestone at every MILESTONE_STEP and at the final item
        if done % MILESTONE_STEP == 0 or idx == n_items:
            cum_runtime = time.perf_counter() - batch_start
            avg_t_so_far = sum(r["elapsed"] for r in results) / done
            milestones.append({
                "n_solved":        done,
                "avg_time_s":      round(avg_t_so_far, 4),
                "cumulative_runtime_s": round(cum_runtime, 2),
            })

        # Progress every 50 items
        if idx % 50 == 0 or idx == n_items:
            avg  = sum(r["elapsed"] for r in results) / done
            print(f"  [{idx:>5}/{n_items}]  solved={done:>5}  "
                  f"avg_time={avg:.3f}s", flush=True)

    batch_time = time.perf_counter() - batch_start

    # ── (0) Runtime / optimality table ────────────────────────────────────
    times     = [r["elapsed"] for r in results]
    statuses  = [r["status"]  for r in results]
    n_solved  = len(results)
    n_optimal = statuses.count("Optimal")
    n_infeas  = statuses.count("Infeasible")
    n_other   = n_solved - n_optimal - n_infeas
    gap_pct   = (1 - n_optimal / n_solved) * 100 if n_solved else 100

    avg_t = sum(times) / n_solved if n_solved else 0
    min_t = min(times)
    max_t = max(times)

    W = 48
    SEP = "─" * W
    def row(label, val): print(f"  {label:<40} {val:>6}")

    print(f"\n{'═'*W}")
    print(f"  BENCHMARK RESULTS — REAL DATA")
    print(f"{'═'*W}")
    print(f"  {'Metric':<40} {'Value':>6}")
    print(SEP)
    row("Number of item-level problems",   f"{n_solved:,}")
    row("Average solving time (s)",        f"{avg_t:.2f}")
    row("Minimum solving time (s)",        f"{min_t:.2f}")
    row("Maximum solving time (s)",        f"{max_t:.2f}")
    row("Total batch runtime (s)",         f"{batch_time:.0f}")
    row("Optimal solutions",               f"{n_optimal:,}")
    row("Infeasible solutions",            f"{n_infeas:,}")
    row("Other (timeout / failed)",        f"{n_other:,}")
    row("Optimality gap",                  "0%" if n_optimal == n_solved else f"{gap_pct:.1f}%")
    print(f"{'═'*W}")

    # ── (1) Cost structure summary ─────────────────────────────────────────
    opt_res = [r for r in results if r["status"] == "Optimal"]
    objs        = [r["obj"]      for r in opt_res]
    cost_bo_all = [r["cost_bo"]  for r in opt_res]
    cost_o_all  = [r["cost_o"]   for r in opt_res]
    cost_s_all  = [r["cost_s"]   for r in opt_res]
    cost_p_all  = [r["cost_p"]   for r in opt_res]

    n_opt = len(opt_res)
    avg_obj    = sum(objs)        / n_opt if n_opt else 0
    total_obj  = sum(objs)
    total_bo   = sum(cost_bo_all)
    total_o    = sum(cost_o_all)
    total_s    = sum(cost_s_all)
    total_p    = sum(cost_p_all)
    total_cost = total_bo + total_o + total_s + total_p

    def pct(x): return f"{100*x/total_cost:.1f}%" if total_cost > 0 else "N/A"

    # items with any non-zero cost per type
    n_has_bo = sum(1 for v in cost_bo_all if v > 0.001)
    n_has_o  = sum(1 for v in cost_o_all  if v > 0.001)
    n_has_s  = sum(1 for v in cost_s_all  if v > 0.001)
    n_has_p  = sum(1 for v in cost_p_all  if v > 0.001)

    print(f"\n{'═'*W}")
    print(f"  (1) COST STRUCTURE SUMMARY  (n={n_opt:,} optimal items)")
    print(f"{'═'*W}")
    print(f"  {'Metric':<40} {'Value':>6}")
    print(SEP)
    row("Average objective value",         f"{avg_obj:.2f}")
    row("Total objective (all items)",     f"{total_cost:,.1f}")
    print(SEP)
    row("Backorder cost  (total)",         f"{total_bo:,.1f}")
    row("  % of total cost",               pct(total_bo))
    row("  Items incurring backorder",     f"{n_has_bo:,} ({100*n_has_bo/n_opt:.1f}%)")
    print()
    row("Overstock cost  (total)",         f"{total_o:,.1f}")
    row("  % of total cost",               pct(total_o))
    row("  Items incurring overstock",     f"{n_has_o:,} ({100*n_has_o/n_opt:.1f}%)")
    print()
    row("Shortage cost   (total)",         f"{total_s:,.1f}")
    row("  % of total cost",               pct(total_s))
    row("  Items incurring shortage",      f"{n_has_s:,} ({100*n_has_s/n_opt:.1f}%)")
    print()
    row("Penalty cost    (total)",         f"{total_p:,.1f}")
    row("  % of total cost",               pct(total_p))
    row("  Items incurring penalty",       f"{n_has_p:,} ({100*n_has_p/n_opt:.1f}%)")
    print(f"{'═'*W}")

    # ── (2) Allocation behaviour statistics ────────────────────────────────
    # Flatten all periods across all optimal items
    all_periods = [per for r in opt_res for per in r["periods"]]
    n_periods   = len(all_periods)  # = n_opt * |T|

    n_dominant  = sum(1 for p in all_periods if p["dominant"])
    n_residual  = sum(1 for p in all_periods if p["has_residual"])
    n_bo_period = sum(1 for p in all_periods if p["has_bo"])

    print(f"\n{'═'*W}")
    print(f"  (2) ALLOCATION BEHAVIOUR STATISTICS")
    print(f"      (total periods analysed = {n_periods:,} = {n_opt}×{len(T)})")
    print(f"{'═'*W}")
    print(f"  {'Metric':<40} {'Value':>6}")
    print(SEP)
    row("Periods with >70% CAP to 1 WH",
        f"{n_dominant:,} ({100*n_dominant/n_periods:.1f}%)")
    row("Periods with residual units (r>0)",
        f"{n_residual:,} ({100*n_residual/n_periods:.1f}%)")
    row("Periods with backorder (bo>0)",
        f"{n_bo_period:,} ({100*n_bo_period/n_periods:.1f}%)")
    print(f"{'═'*W}")

    # ── Save detailed CSV ────────────────────────────────────────────────
    out_csv = Path(__file__).parent / "benchmark_results.csv"
    pd.DataFrame([
        {"item": r["item"], "status": r["status"], "time_s": r["elapsed"],
         "objective": r["obj"], "cost_backorder": r["cost_bo"],
         "cost_overstock": r["cost_o"], "cost_shortage": r["cost_s"],
         "cost_penalty": r["cost_p"]}
        for r in results
    ]).to_csv(out_csv, index=False)
    print(f"\nChi tiết lưu tại:  {out_csv}")

    # ── Save & plot milestones ───────────────────────────────────────────
    ms_df  = pd.DataFrame(milestones)
    ms_csv = Path(__file__).parent / "benchmark_milestones.csv"
    ms_df.to_csv(ms_csv, index=False)
    print(f"Milestones CSV:    {ms_csv}")

    xs   = ms_df["n_solved"].tolist()
    avg_ = ms_df["avg_time_s"].tolist()
    cum_ = ms_df["cumulative_runtime_s"].tolist()

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.suptitle("SS-MB-SMI Solver Performance — Real Data",
                 fontsize=13, fontweight="bold")

    # Panel 1 – average solving time per subproblem
    ax1 = axes[0]
    ax1.plot(xs, avg_, marker="o", color="steelblue",
             linewidth=2, markersize=6, zorder=3)
    ax1.fill_between(xs, avg_, alpha=0.15, color="steelblue")
    for x, y in zip(xs, avg_):
        ax1.annotate(f"{y:.3f}s", (x, y), textcoords="offset points",
                     xytext=(0, 7), ha="center", fontsize=8, color="steelblue")
    ax1.set_title("Average Solving Time per Subproblem")
    ax1.set_xlabel("Number of items solved")
    ax1.set_ylabel("Avg time (s)")
    ax1.set_xticks(xs)
    ax1.set_xticklabels([str(x) for x in xs], rotation=45, ha="right")
    ax1.grid(axis="y", linestyle="--", alpha=0.4)
    ax1.set_ylim(bottom=0, top=max(avg_) * 1.4)

    # Panel 2 – cumulative batch runtime
    ax2 = axes[1]
    ax2.plot(xs, cum_, marker="s", color="darkorange",
             linewidth=2, markersize=6, zorder=3)
    ax2.fill_between(xs, cum_, alpha=0.15, color="darkorange")
    for x, y in zip(xs, cum_):
        ax2.annotate(f"{y:.0f}s", (x, y), textcoords="offset points",
                     xytext=(0, 7), ha="center", fontsize=8, color="darkorange")
    ax2.set_title("Cumulative Batch Runtime")
    ax2.set_xlabel("Number of items solved")
    ax2.set_ylabel("Cumulative time (s)")
    ax2.set_xticks(xs)
    ax2.set_xticklabels([str(x) for x in xs], rotation=45, ha="right")
    ax2.grid(axis="y", linestyle="--", alpha=0.4)
    ax2.set_ylim(bottom=0, top=max(cum_) * 1.15)

    plt.tight_layout()
    chart_path = Path(__file__).parent / "benchmark_chart.png"
    plt.savefig(chart_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Chart PNG:         {chart_path}")


if __name__ == "__main__":
    main()
