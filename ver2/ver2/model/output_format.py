"""
output_format.py
================
Formats model results into:
  1. schedule.csv  - weekly inventory calendar (1 row per WH per period)
  2. costs.csv     - cost breakdown per WH per period
"""
import os
import csv

def write_schedule(results, params, output_dir):
    """
    Writes schedule.csv - inventory calendar.
    """
    filename = os.path.join(output_dir, "schedule.csv")
    
    meta = params.get("meta", {})
    warehouses = meta.get("warehouses", [])
    T = meta.get("T", 0)
    
    # Pre-calculate OA/PLT lead times if static
    oa_lead_default = params.get("OA_lead", 8)
    
    with open(filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        header = [
            "week", "warehouse", "inv_begin", 
            "L", "U",
            "Q_OA_allocated", "Q_OA_received", 
            "PLT_in", "PLT_out", 
            "delta_I", "inventory_end", 
            "surplus_E", "backorder", "shortage", "overstock", 
            "PLT_detail"
        ]
        writer.writerow(header)
        
        for t in range(1, T + 1):
            for i in warehouses:
                # 1. inv_begin
                if t == 1:
                    inv_begin = params.get("BI", {}).get(i, 0)
                else:
                    inv_begin = results.get("I", {}).get(f"{i}_t{t-1}", 0)
                
                # lead times
                oa_lead_i = params.get("OA_lead", {}).get(i, oa_lead_default) if isinstance(params.get("OA_lead"), dict) else oa_lead_default
                
                # 2. Q_OA_allocated
                q_oa_alloc = results.get("Q_OA", {}).get(f"{i}_t{t}", 0)
                
                # 3. Q_OA_received
                # Actually, OA shipped at t - oa_lead_i is received at t
                q_oa_recv = 0
                if t - oa_lead_i >= 1:
                    q_oa_recv = results.get("Q_OA", {}).get(f"{i}_t{t-oa_lead_i}", 0)
                
                # 4. PLT_in / PLT_out
                plt_in = 0
                plt_out = 0
                plt_details = []
                for j in warehouses:
                    if i == j: continue
                    # PLT out from i to j at time t
                    out_val = results.get("Q_PLT", {}).get(f"{i}_{j}_t{t}", 0)
                    plt_out += out_val
                    if out_val > 0:
                        plt_details.append(f"{j}: {out_val}")
                        
                    # PLT in from j to i arriving at time t
                    # Sent at t - lead_time
                    plt_lead = params.get("PLT_lead", {}).get(f"{j}_{i}", 2)
                    if t - plt_lead >= 1:
                        in_val = results.get("Q_PLT", {}).get(f"{j}_{i}_t{t-plt_lead}", 0)
                        if in_val > 0:
                            plt_in += in_val
                            plt_details.append(f"from {j}: {in_val}")
                
                plt_detail_str = " | ".join(plt_details)
                
                # 5. delta_I
                delta_i = params.get("delta_I", {}).get(f"{i}_{t}", 0)
                
                # 6. Variables at t
                inv_end = results.get("I", {}).get(f"{i}_t{t}", 0)
                surplus = results.get("E", {}).get(f"{i}_t{t}", 0)
                backorder = results.get("bo", {}).get(f"{i}_t{t}", 0)
                shortage = results.get("s", {}).get(f"{i}_t{t}", 0)
                overstock = results.get("o", {}).get(f"{i}_t{t}", 0)
                
                L_val = params.get("L", {}).get(f"{i}_{t}", 0)
                U_val = params.get("U", {}).get(f"{i}_{t}", 1000)
                
                row = [
                    t, i, inv_begin,
                    L_val, U_val,
                    q_oa_alloc, q_oa_recv,
                    plt_in, plt_out,
                    delta_i, inv_end,
                    surplus, backorder, shortage, overstock,
                    plt_detail_str
                ]
                writer.writerow(row)

def write_costs(results, params, output_dir):
    """
    Writes costs.csv - detailed cost per WH per period.
    """
    filename = os.path.join(output_dir, "costs.csv")
    
    meta = params.get("meta", {})
    warehouses = meta.get("warehouses", [])
    T = meta.get("T", 0)
    tc_rate = params.get("TC", 0)
    
    total_cost_all = 0.0
    
    with open(filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        header = [
            "week", "warehouse", 
            "overstock_cost", "shortage_cost", "backorder_cost", 
            "penalty_OA_cost", "PLT_penalty_cost", "transport_cost", 
            "total_cost"
        ]
        writer.writerow(header)
        
        for t in range(1, T + 1):
            for i in warehouses:
                c_over = params.get("cost", {}).get(i, {}).get(str(t), {}).get("overstock", 0)
                c_short = params.get("cost", {}).get(i, {}).get(str(t), {}).get("shortage", 0)
                c_bo = params.get("cost", {}).get(i, {}).get(str(t), {}).get("backorder", 0)
                c_pen = params.get("cost", {}).get(i, {}).get(str(t), {}).get("penalty", 0)
                
                overstock_qty = results.get("o", {}).get(f"{i}_t{t}", 0)
                shortage_qty = results.get("s", {}).get(f"{i}_t{t}", 0)
                bo_qty = results.get("bo", {}).get(f"{i}_t{t}", 0)
                pOA = results.get("pOA", {}).get(f"{i}_t{t}", 0)
                
                cost_o = c_over * overstock_qty
                cost_s = c_short * shortage_qty
                cost_bo = c_bo * bo_qty
                cost_poa = c_pen * pOA
                
                cost_pplt = 0
                cost_trans = 0
                
                for j in warehouses:
                    if i == j: continue
                    c_pen_j = params.get("cost", {}).get(j, {}).get(str(t), {}).get("penalty", 0)
                    dist = params.get("distance", {}).get(f"{i}_{j}", 0)
                    
                    pPLT = results.get("pPLT", {}).get(f"{i}_{j}_t{t}", 0)
                    x_val = results.get("x", {}).get(f"{i}_{j}_t{t}", 0)
                    
                    cost_pplt += c_pen_j * pPLT
                    cost_trans += dist * tc_rate * x_val
                
                row_total = cost_o + cost_s + cost_bo + cost_poa + cost_pplt + cost_trans
                total_cost_all += row_total
                
                row = [
                    t, i,
                    cost_o, cost_s, cost_bo,
                    cost_poa, cost_pplt, cost_trans,
                    row_total
                ]
                writer.writerow(row)

def print_inventory_table(results, params):
    """
    In ra bảng tồn kho theo tuần (console) - dạng lịch.
    """
    meta = params.get("meta", {})
    warehouses = meta.get("warehouses", [])
    T = meta.get("T", 0)
    
    print("\n" + "="*60)
    print(f" Generated Case: {meta.get('label', '')}")
    print(" Inventory Schedule:")
    
    for i in warehouses:
        print(f"\n WH: {i}")
        header = "Week | " + " | ".join(f"t={t:<3}" for t in range(1, T+1))
        print("-" * len(header))
        print(header)
        
        invs = []
        for t in range(1, T+1):
            val = results.get("I", {}).get(f"{i}_t{t}", 0)
            invs.append(f"{val:>5.0f}")
        
        print("Inv  | " + " | ".join(invs))
        
    print("="*60 + "\n")

