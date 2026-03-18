"""
Test 3 trường hợp so sánh Proportional Allocation vs MILP:

  Case 1 (case_milp_wins): MILP tốt hơn Proportional
    - 2 kỳ, nhu cầu lệch giữa các kỳ → MILP "nhìn trước" được
  Case 2 (case_equal): MILP = Proportional
    - 1 kỳ, 2 kho đối xứng → không có lợi thế multi-period
  Case 3 (case_timeout): MILP bị cắt sớm (time_limit=1s)
    - 50 SP × 6 kho × 8 kỳ, solver chưa kịp tìm optimal

Chạy:
  docker exec smi_backend python /app/data_test/test_proportional_vs_milp.py
"""
import sys
import os
import time as _time

# Thêm project root vào path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.data_access.csv_repository import CsvOptimizationDataRepository
from backend.domain.services import _baseline_cost, _proportional_allocation_cost
from optimization.models.ss_mb_smi import solve_ss_mb_smi, _solve_item
import pulp


def run_case(case_name: str, data_dir: str, time_limit: int = 30, verbose: bool = True):
    """Chạy 1 test case, trả về dict kết quả."""
    print(f"\n{'='*70}")
    print(f"  {case_name}")
    print(f"{'='*70}")

    # ── Load data ──
    repo = CsvOptimizationDataRepository(data_dir)
    data = repo.get_optimization_input()
    n_products = len(data.I)
    n_warehouses = len(data.J)
    n_periods = len(data.T)
    n_cells = n_products * n_warehouses * n_periods

    print(f"\n  [DATA]")
    print(f"  Sản phẩm: {n_products}, Kho: {n_warehouses}, Kỳ: {n_periods}")
    print(f"  Tổng ô (i,j,t): {n_cells}")
    print(f"  Solver time limit: {time_limit}s per item")

    # ── Log dữ liệu đầu vào (chỉ khi ít sản phẩm) ──
    if verbose and n_products <= 5:
        print(f"\n  [INPUT DETAIL]")
        for i in sorted(data.I):
            for j in sorted(data.J):
                bi = data.BI.get((i, j), 0)
                cp = data.CP.get((i, j), 1)
                print(f"  {i}/{j}: BI={bi}, CP={cp}")
                for t in sorted(data.T):
                    di = data.DI.get((i, j, t), 0)
                    u = data.U.get((i, j, t), 0)
                    l = data.L.get((i, j, t), 0)
                    cap = data.CAP.get((i, t), 0)
                    co = data.Co.get((i, j, t), 0)
                    cs = data.Cs.get((i, j, t), 0)
                    cb = data.Cb.get((i, j, t), 0)
                    cp_cost = data.Cp.get((i, j, t), 0)
                    print(f"    t={t}: DI={di:+}, U={u}, L={l}, CAP={cap}"
                          f" | Co={co}, Cs={cs}, Cb={cb}, Cp={cp_cost}")

    # ── Solve MILP (per-item decomposition) ──
    print(f"\n  [MILP SOLVING]")
    t0 = _time.time()
    sol = solve_ss_mb_smi(data, time_limit_per_item=time_limit)
    milp_cost = sol.objective_value
    milp_status = sol.solver_status
    milp_time = sol.solve_time_seconds

    # Log per-item status nếu có lỗi
    if sol.n_infeasible > 0 or sol.n_failed > 0:
        print(f"  ⚠ Có items không đạt Optimal — chạy lại để log chi tiết:")
        T = sorted(data.T)
        status_counts = {}
        failed_items = []
        for item in sorted(data.I):
            j_list = sorted(set(j for (i, j, t) in data.DI.keys() if i == item))
            if not j_list:
                continue
            result = _solve_item(
                item, j_list, T, data.BI, data.DI, data.U, data.L,
                data.CAP, data.CP, data.Co, data.Cs, data.Cb, data.Cp,
                getattr(data, "HV", 9999.0), time_limit,
            )
            st = result["status"]
            status_counts[st] = status_counts.get(st, 0) + 1
            if st != "Optimal":
                failed_items.append((item, st))

        print(f"  Status breakdown: {status_counts}")
        if len(failed_items) <= 10:
            for item, st in failed_items:
                print(f"    {item}: {st}")
        else:
            print(f"    (hiển thị 10/{len(failed_items)} items đầu tiên)")
            for item, st in failed_items[:10]:
                print(f"    {item}: {st}")

    # Log nghiệm MILP chi tiết (khi ít SP)
    if verbose and n_products <= 5 and milp_status == "Optimal":
        print(f"\n  [MILP SOLUTION DETAIL]")
        for (i, j, t) in sorted(sol.Q_sol.keys()):
            q = sol.Q_sol.get((i, j, t), 0)
            r = sol.R_sol.get((i, j, t), 0)
            inv = sol.INV.get((i, j, t), 0)
            bo = sol.BO_sol.get((i, j, t), 0)
            o = sol.O_sol.get((i, j, t), 0)
            s = sol.S_sol.get((i, j, t), 0)
            p = sol.PE_sol.get((i, j, t), 0)
            cp = data.CP.get((i, j), 1)
            shipped = q * cp + r
            print(f"  {i}/{j}/t={t}: q={q}, r={r}, shipped={shipped}"
                  f" | I={inv:.1f}, bo={bo:.1f}, o={o:.1f}, s={s:.1f}, p={p}")

    # ── Proportional allocation ──
    print(f"\n  [PROPORTIONAL ALLOCATION]")
    prop_cost = _proportional_allocation_cost(data)

    # ── Baseline (do-nothing) ──
    baseline_cost = _baseline_cost(data)

    # ── So sánh ──
    if prop_cost > 0:
        savings_vs_prop = (prop_cost - milp_cost) / prop_cost * 100
    else:
        savings_vs_prop = 0

    if baseline_cost > 0:
        savings_vs_base = (baseline_cost - milp_cost) / baseline_cost * 100
    else:
        savings_vs_base = 0

    print(f"\n  {'─'*60}")
    print(f"  KẾT QUẢ")
    print(f"  {'─'*60}")
    print(f"  MILP status:          {milp_status}")
    print(f"  MILP solve time:      {milp_time:.3f}s")
    print(f"  Items optimal:        {n_products - sol.n_infeasible - sol.n_failed}/{n_products}")
    print(f"  Items infeasible:     {sol.n_infeasible}")
    print(f"  Items failed/timeout: {sol.n_failed}")
    print(f"  {'─'*60}")
    print(f"  Do-nothing cost:      {baseline_cost:>15,.2f}")
    print(f"  Proportional cost:    {prop_cost:>15,.2f}")
    print(f"  MILP cost:            {milp_cost:>15,.2f}")
    print(f"  {'─'*60}")
    print(f"  MILP vs Do-nothing:   {savings_vs_base:>+.2f}%")
    print(f"  MILP vs Proportional: {savings_vs_prop:>+.2f}%")

    # ── Verdict ──
    if milp_status == "Optimal" and abs(savings_vs_prop) < 0.01:
        verdict = "BANG NHAU — Proportional trung optimal"
    elif milp_status == "Optimal" and savings_vs_prop > 0:
        verdict = "MILP THANG — Toi uu da ky tot hon heuristic"
    elif milp_status != "Optimal":
        verdict = (f"MILP BI CAT SOM (status={milp_status}, "
                   f"{sol.n_failed} failed, {sol.n_infeasible} infeasible)")
    else:
        verdict = "KET QUA BAT THUONG — can kiem tra"

    print(f"\n  >>> VERDICT: {verdict}")

    return {
        "case": case_name,
        "milp_status": milp_status,
        "milp_cost": milp_cost,
        "prop_cost": prop_cost,
        "baseline_cost": baseline_cost,
        "savings_vs_prop": savings_vs_prop,
        "savings_vs_base": savings_vs_base,
        "n_optimal": n_products - sol.n_infeasible - sol.n_failed,
        "n_infeasible": sol.n_infeasible,
        "n_failed": sol.n_failed,
        "solve_time": milp_time,
        "verdict": verdict,
    }


def main():
    data_test_dir = os.path.dirname(os.path.abspath(__file__))

    results = []

    # ── Case 1: MILP thắng ──────────────────────────────────────
    # 1 SP (T001), 2 kho (WH01, WH02), 2 kỳ, CP=4, CAP=20
    #
    # Kỳ 1: WH01 DI=-10 (bán mạnh), WH02 DI=-5 (bán ít)
    # Kỳ 2: WH01 DI=-2  (bán ít),   WH02 DI=-20 (bán mạnh)
    #
    # Proportional kỳ 1: deficit WH01=13, WH02=8 → chia 20 theo tỉ lệ
    #   → WH01 nhận nhiều hơn (vì hiện tại thiếu hơn)
    # MILP nhìn trước: kỳ 2 WH02 sẽ thiếu nặng → kỳ 1 dành cho WH02
    #   → tổng chi phí thấp hơn
    results.append(run_case(
        "Case 1: MILP THANG (multi-period trade-off)",
        os.path.join(data_test_dir, "case_milp_wins"),
        time_limit=30,
    ))

    # ── Case 2: Bằng nhau ───────────────────────────────────────
    # 1 SP (T001), 2 kho (WH01, WH02), 1 kỳ duy nhất
    # Hoàn toàn đối xứng: BI=0, DI=-8, L=8, U=40, CP=4
    # CAP=16 → deficit mỗi kho = 16, chia đều = 8, floor(8/4)×4 = 8
    # → Proportional chọn đúng nghiệm optimal → chi phí bằng nhau
    results.append(run_case(
        "Case 2: BANG NHAU (doi xung, 1 ky)",
        os.path.join(data_test_dir, "case_equal"),
        time_limit=30,
    ))

    # ── Case 3: MILP bị cắt sớm ────────────────────────────────
    # 50 SP × 6 kho × 8 kỳ = 2,400 ô
    # time_limit=1s per item
    #
    # Lưu ý: Model dùng per-item decomposition nên mỗi sub-problem
    # chỉ có 6 kho × 8 kỳ = 48 bộ biến. CBC thường giải trong < 1s.
    # Một số items có dữ liệu random khó (CAP/CP không khớp) có thể
    # trả về status != Optimal khi bị giới hạn thời gian.
    results.append(run_case(
        "Case 3: MILP BI CAT SOM (50x6x8, time=1s)",
        os.path.join(data_test_dir, "case_timeout"),
        time_limit=1,
        verbose=False,  # quá nhiều SP để log chi tiết
    ))

    # ── Tổng kết ────────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print("  TONG KET 3 TRUONG HOP")
    print(f"{'='*70}")
    print(f"  {'Case':<42} {'Status':<12} {'vs Prop':>9} {'vs Base':>9} {'Time':>7}")
    print(f"  {'─'*79}")
    for r in results:
        print(f"  {r['case']:<42} {r['milp_status']:<12} "
              f"{r['savings_vs_prop']:>+8.2f}% {r['savings_vs_base']:>+8.2f}% "
              f"{r['solve_time']:>6.2f}s")
        if r['n_failed'] > 0 or r['n_infeasible'] > 0:
            print(f"    └─ Optimal: {r['n_optimal']}, "
                  f"Failed: {r['n_failed']}, Infeasible: {r['n_infeasible']}")
    print(f"  {'─'*79}")

    print(f"\n  Giai thich:")
    print(f"  - vs Prop > 0%:  MILP re hon Proportional (MILP thang)")
    print(f"  - vs Prop = 0%:  MILP bang Proportional")
    print(f"  - vs Base:       MILP re hon Do-nothing (luon > 0%)")
    print()


if __name__ == "__main__":
    main()
