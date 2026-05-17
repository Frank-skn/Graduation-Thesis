import json
import os
import sys
import time
import argparse

# Make sure model/ is on path when run from version 2/
sys.path.insert(0, os.path.dirname(__file__))

from oa_plt_milp    import OA_PLT_Model
from output_format  import write_schedule, write_costs, print_inventory_table
from excel_export   import export_master_excel

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_DIR = os.path.join(BASE_DIR, "test data")
OUTPUT_DIR  = os.path.join(BASE_DIR, "output")

TIME_LIMIT  = 300   # seconds per case


def load_test_cases(test_data_dir: str):
    """Đọc toàn bộ case test từ test data/case_*/input/parameters.json."""
    cases = []

    if not os.path.exists(test_data_dir):
        return cases

    for entry in sorted(os.listdir(test_data_dir)):
        case_dir = os.path.join(test_data_dir, entry)
        if not os.path.isdir(case_dir):
            continue

        params_path = os.path.join(case_dir, "input", "parameters.json")
        if not os.path.exists(params_path):
            continue

        with open(params_path, "r", encoding="utf-8") as f:
            params = json.load(f)

        case_name = params.get("meta", {}).get("case", entry)
        cases.append((case_name, params))

    return cases

def calculate_baseline_cost(params):
    """Tính toán chi phí nếu không can thiệp (chỉ để hao hụt tự nhiên)"""
    cost = 0
    whs = params["meta"]["warehouses"]
    T = params["meta"]["T"]
    
    for wh in whs:
        baseline = params["BI"][wh]
        for t in range(1, T+1):
            baseline += params["delta_I"].get(f"{wh}_{t}", 0)
            
            L = params["L"].get(f"{wh}_{t}", 0)
            U = params["U"].get(f"{wh}_{t}", 0)
            
            # Using cost params
            overstock_cost = params["cost"][wh][str(t)]["overstock"]
            shortage_cost = params["cost"][wh][str(t)]["shortage"]
            backorder_cost = params["cost"][wh][str(t)]["backorder"]
            
            if baseline > U:
                cost += (baseline - U) * overstock_cost
            if baseline < L and baseline >= 0:
                cost += (L - baseline) * shortage_cost
            if baseline < 0:
                s = L - baseline
                b = -baseline
                cost += s * shortage_cost + b * backorder_cost
                
    return cost

def run_case(params: dict, case_name: str, out_dir: str, verbose: bool = True, current_idx: int = 1, total_cases: int = 1):
    if verbose:
        print(f"\n{'='*65}")
        print(f"  Running {case_name.upper()} ({current_idx}/{total_cases})")
        print(f"  Lưu tại: {out_dir}")
        print(f"{'='*65}")

    meta = params["meta"]
    if verbose:
        print(f"  Product   : {meta['product']}")
        print(f"  Warehouses: {meta['warehouses']}")
        print(f"  T         : {meta['T']} periods")

    # ── Build & solve ────────────────────────────────────────────────────────
    model  = OA_PLT_Model(params)
    model.build()
    
    start_time = time.time()
    status = model.solve(time_limit=TIME_LIMIT, msg=1 if verbose else 0)
    end_time = time.time()
    solve_duration = end_time - start_time

    if status != "Optimal":
        raise RuntimeError(f"Solver returned non-optimal status for {case_name}: {status}")

    results = model.get_results()

    # ── Output directory ─────────────────────────────────────────────────────
    os.makedirs(out_dir, exist_ok=True)

    # Console inventory table
    if verbose:
        print_inventory_table(results, params)
    
    # Text/CSV files
    write_schedule(results, params, out_dir)
    write_costs(results, params, out_dir)

    raw_path = os.path.join(out_dir, "results_raw.json")
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    cost_before = calculate_baseline_cost(params)
    cost_after = results['objective']

    if verbose:
        print(f"  → results_raw.json")
        print(f"  Cost Before: {cost_before:,.2f} | Cost After: {cost_after:,.2f}")
        print(f"  Solve Time : {solve_duration:,.2f}s")
    
    return {
        'case_name': case_name,
        'solve_time': solve_duration,
        'cost_before': cost_before,
        'cost_after': cost_after,
        'results': results,
        'params': params
    }

def main():
    parser = argparse.ArgumentParser(description="Run OA+PLT MILP Master cases")
    parser.add_argument("--quiet", action="store_true", help="Suppress solver output")
    args = parser.parse_args()

    if not os.path.exists(TEST_DATA_DIR):
        print(f"Không tìm thấy thư mục test data tại {TEST_DATA_DIR}!")
        return

    print("Đang đọc dữ liệu test từ parameters.json...")
    cases = load_test_cases(TEST_DATA_DIR)
    
    if not cases:
        print("Không tìm thấy case test nào trong test data!")
        return

    total_files = len(cases)
    all_runs = []
    
    print(f"\nBắt đầu chạy {total_files} cases...")
    
    for idx, (case_name, params) in enumerate(cases, 1):
        out_dir = os.path.join(OUTPUT_DIR, case_name)
        
        run_data = run_case(params, case_name, out_dir, verbose=not args.quiet, current_idx=idx, total_cases=total_files)
        all_runs.append(run_data)
        # In tiến độ lên terminal
        sys.stdout.write(f"\rTiến độ: {idx}/{total_files} cases đã hoàn thành.")
        sys.stdout.flush()

    print("\nEnd.")

    print(f"\n{'='*65}")
    print(f"  Tất cả kịch bản đã giải xong. Tiến hành xuất Excel Master...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    export_master_excel(all_runs, OUTPUT_DIR)
    
    print(f"  Hoàn tất toàn bộ công việc!")
    print(f"{'='*65}\n")

if __name__ == "__main__":
    main()
