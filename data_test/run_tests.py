"""
Chạy toàn bộ 12 test case SS-MB-SMI và in kết quả chi tiết.
Sử dụng: python run_tests.py   (từ thư mục data_test)
"""
import sys
from pathlib import Path
import pandas as pd
import pulp

HV = 9999
T_ALL = [1, 2, 3, 4]

CASE_DESCRIPTIONS = {
    "case01": "DI âm rủi ro: WH01 BI=10,DI_t1=-40 (âm nặng); WH02/03 DI=-3/T. CP=4,CAP=12. Cb=200,Cp=100",
    "case02": "2 kho overstock: WH01 BI=35,WH02 BI=32 (>U=25), DI=0; WH03 BI=12,DI=-5/T. CP=4,CAP=8. Cb=200,Cp=100",
    "case03": "CAP lẻ vs CP: CAP=13, CP=4 (13=3×4+1) → buộc r≥1 ở 1 kho/T → penalty. Cb=200,Cp=100",
}

SEPARATOR = "=" * 72

def as_str(v): return str(v).strip()
def safe(v):
    x = pulp.value(v)
    return 0.0 if x is None else float(x)

def read(d: Path, name: str, dtype=None) -> pd.DataFrame:
    df = pd.read_csv(d / f"{name}.csv", dtype=dtype)
    df.columns = df.columns.str.strip().str.lower()
    return df

# ---------------------------------------------------------------------------
def run_case(case_dir: Path):
    name = case_dir.name
    print(f"\n{SEPARATOR}")
    print(f"  TEST {name.upper()}  |  {CASE_DESCRIPTIONS.get(name, '')}")
    print(SEPARATOR)

    # ---- LOAD DATA ----
    inv_begin = read(case_dir, "inventory_begin", dtype={"product_id": str, "warehouse_id": str})
    inv_flow  = read(case_dir, "inventory_flow",  dtype={"product_id": str, "warehouse_id": str})
    uc        = read(case_dir, "unit_cost",        dtype={"product_id": str, "warehouse_id": str})
    pack_det  = read(case_dir, "packing_details",  dtype={"product_id": str})
    box_ship  = read(case_dir, "box_shipment",     dtype={"warehouse_id": str})
    ven_cap   = read(case_dir, "vendor_capacity",  dtype={"product_id": str})
    tp        = read(case_dir, "time_period")

    for df, cols in ((inv_begin, ("product_id","warehouse_id")),
                     (inv_flow,  ("product_id","warehouse_id")),
                     (uc,        ("product_id","warehouse_id")),
                     (pack_det,  ("product_id",)),
                     (box_ship,  ("warehouse_id",))):
        for c in cols:
            df[c] = df[c].map(as_str)

    tp["time_period"]         = tp["time_period"].astype(int)
    inv_flow["time_period"]   = inv_flow["time_period"].astype(int)
    uc["time_period"]         = uc["time_period"].astype(int)
    ven_cap["time_period"]    = ven_cap["time_period"].astype(int)

    T  = sorted(tp["time_period"].unique().tolist())
    IJ = sorted(set(zip(inv_flow["product_id"], inv_flow["warehouse_id"])))
    J_by_i: dict[str, list[str]] = {}
    for i_, j_ in IJ:
        J_by_i.setdefault(i_, []).append(j_)
    I_list = sorted({i_ for i_, _ in IJ})
    assert len(I_list) == 1, "Test case phải có đúng 1 item!"
    item = I_list[0]
    j_list = J_by_i[item]

    # ---- PARAMETERS ----
    BI = {(as_str(r.product_id), as_str(r.warehouse_id)): float(r.beginning_inventory)
          for _, r in inv_begin.iterrows()}
    U, L, DI = {}, {}, {}
    for _, r in inv_flow.iterrows():
        k = (as_str(r.product_id), as_str(r.warehouse_id), int(r.time_period))
        U[k] = float(r.inventory_ceiling)
        L[k] = float(r.inventory_floor)
        DI[k] = float(r.inventory_fluctuation)
    CAP = {(as_str(r.product_id), int(r.time_period)): float(r.capacity)
           for _, r in ven_cap.iterrows()}
    Co, Cs, Cb, Cp = {}, {}, {}, {}
    for _, r in uc.iterrows():
        k = (as_str(r.product_id), as_str(r.warehouse_id), int(r.time_period))
        Co[k] = float(r.overstock_cost);  Cs[k] = float(r.shortage_cost)
        Cb[k] = float(r.backlog_cost);    Cp[k] = float(r.penalty_cost)

    pack_det = pack_det.reset_index(drop=True)
    pack_det.index = pack_det.index + 1
    pack_lookup = {int(idx): (as_str(r.product_id), int(r.pack_multiple))
                   for idx, r in pack_det.iterrows()}
    active = box_ship[box_ship["is_active"].astype(str).str.lower().eq("true")]
    CP_param: dict[tuple, int] = {}
    for _, r in active.iterrows():
        pd_id = int(r.packing_details_id)
        if pd_id in pack_lookup:
            ip, cpv = pack_lookup[pd_id]
            CP_param[(ip, as_str(r.warehouse_id))] = cpv

    # ---- PRINT INPUT ----
    print(f"\n{'─'*40}")
    print("INPUT PARAMETERS")
    print(f"{'─'*40}")
    print(f"Item : {item}")
    print(f"T    : {T}")
    print(f"WH   : {j_list}")
    print()
    print(f"{'':6} {'WH':>6} | {'BI':>6} | {'CP':>4}")
    print(f"{'':6} {'──':>6}─+─{'──':>6}─+─{'──':>4}")
    for j in j_list:
        print(f"{'':6} {j:>6} | {BI.get((item,j),0):>6.0f} | {CP_param.get((item,j),1):>4d}")
    print()

    print(f"{'T':>4} | {'WH':>6} | {'DI':>5} | {'U':>6} | {'L':>6} | {'Co':>5} | {'Cs':>5} | {'Cb':>5} | {'Cp':>5}")
    print(f"{'──':>4}─+─{'──':>6}─+─{'──':>5}─+─{'──':>6}─+─{'──':>6}─+─{'──':>5}─+─{'──':>5}─+─{'──':>5}─+─{'──':>5}")
    for t in T:
        for j in j_list:
            k = (item, j, t)
            print(f"{t:>4} | {j:>6} | {DI.get(k,0):>5.0f} | {U.get(k,0):>6.1f} | {L.get(k,0):>6.1f} | "
                  f"{Co.get(k,0):>5.1f} | {Cs.get(k,0):>5.1f} | {Cb.get(k,0):>5.1f} | {Cp.get(k,0):>5.1f}")
    print()
    print(f"{'T':>4} | {'CAP':>8}")
    print(f"{'──':>4}─+─{'──':>8}")
    for t in T:
        print(f"{t:>4} | {CAP.get((item,t),0):>8.0f}")

    # ---- BUILD & SOLVE MODEL ----
    ijt = [(item, j, t) for j in j_list for t in T]
    sub = pulp.LpProblem(f"SS_{item}", pulp.LpMinimize)
    q_v = pulp.LpVariable.dicts("q", ijt, lowBound=0, cat="Integer")
    r_v: dict[tuple, pulp.LpVariable] = {}
    for i_, j_, t_ in ijt:
        cp = max(1, int(CP_param.get((i_, j_), 1)))
        r_v[(i_, j_, t_)] = pulp.LpVariable(
            f"r_{i_}_{j_}_{t_}", lowBound=0, upBound=cp - 1, cat="Integer")
    Iv = pulp.LpVariable.dicts("I", ijt, lowBound=None, cat="Continuous")
    bo = pulp.LpVariable.dicts("bo", ijt, lowBound=0, cat="Continuous")
    o_v = pulp.LpVariable.dicts("o",  ijt, lowBound=0, cat="Continuous")
    s_v = pulp.LpVariable.dicts("s",  ijt, lowBound=0, cat="Continuous")
    p_v = pulp.LpVariable.dicts("p",  ijt, cat="Binary")

    # Force an LpAffineExpression even when all cost coefficients are zero
    sub += pulp.lpSum(
        Co.get(k, 0)*o_v[k] + Cs.get(k, 0)*s_v[k] +
        Cb.get(k, 0)*bo[k]  + Cp.get(k, 0)*p_v[k]
        for k in ijt) + 0.0 * q_v[ijt[0]]

    t0 = T[0]
    for j in j_list:
        cp = max(1, int(CP_param.get((item, j), 1)))
        sub += Iv[(item,j,t0)] == BI.get((item,j),0) + DI.get((item,j,t0),0) + q_v[(item,j,t0)]*cp + r_v[(item,j,t0)]
        for ki in range(1, len(T)):
            tc, tp = T[ki], T[ki-1]
            sub += Iv[(item,j,tc)] == Iv[(item,j,tp)] + DI.get((item,j,tc),0) + q_v[(item,j,tc)]*cp + r_v[(item,j,tc)]
    for t in T:
        sub += pulp.lpSum(
            q_v[(item,j,t)] * max(1, int(CP_param.get((item,j),1))) + r_v[(item,j,t)]
            for j in j_list) == CAP.get((item,t), 0)
    for j in j_list:
        for t in T:
            sub += bo[(item,j,t)]  >= -Iv[(item,j,t)]
            sub += o_v[(item,j,t)] >= Iv[(item,j,t)] - U.get((item,j,t), 9999)
            sub += s_v[(item,j,t)] >= L.get((item,j,t), 0) - Iv[(item,j,t)]
            sub += r_v[(item,j,t)] <= HV * p_v[(item,j,t)]
            sub += r_v[(item,j,t)] >= HV * (p_v[(item,j,t)] - 1) + 1

    sub.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=30))
    status = pulp.LpStatus[sub.status]

    # ---- PRINT OUTPUT ----
    obj_val = pulp.value(sub.objective)
    obj_str = f"{obj_val:.2f}" if obj_val is not None else "0.00"
    print(f"\n{'─'*40}")
    print(f"GIẢI THUẬT STATUS: {status}   |   Objective = {obj_str}")
    print(f"{'─'*40}")
    print(f"\n{'T':>4} | {'WH':>6} | {'q':>4} | {'r':>4} | {'p':>4} | {'I':>8} | {'bo':>6} | {'o':>6} | {'s':>6} | {'Cost':>10}")
    print(f"{'──':>4}─+─{'──':>6}─+─{'──':>4}─+─{'──':>4}─+─{'──':>4}─+─{'──':>8}─+─{'──':>6}─+─{'──':>6}─+─{'──':>6}─+─{'──':>10}")

    total_cost = 0.0
    for t in T:
        for j in j_list:
            k = (item, j, t)
            qv = int(round(safe(q_v[k])))
            rv = int(round(safe(r_v[k])))
            pv = int(round(safe(p_v[k])))
            iv = safe(Iv[k])
            bv = safe(bo[k])
            ov = safe(o_v[k])
            sv = safe(s_v[k])
            row_cost = (Co.get(k,0)*ov + Cs.get(k,0)*sv +
                        Cb.get(k,0)*bv + Cp.get(k,0)*pv)
            total_cost += row_cost
            cp = max(1, int(CP_param.get((item,j),1)))
            allocated = qv * cp + rv
            cap_check = CAP.get((item,t), 0)
            print(f"{t:>4} | {j:>6} | {qv:>4d} | {rv:>4d} | {pv:>4d} | {iv:>8.1f} | {bv:>6.1f} | {ov:>6.1f} | {sv:>6.1f} | {row_cost:>10.2f}")

        # In kiểm tra ràng buộc capacity
        total_alloc = sum(
            int(round(safe(q_v[(item,j,t)]))) * max(1, int(CP_param.get((item,j),1)))
            + int(round(safe(r_v[(item,j,t)])))
            for j in j_list)
        cap_val = CAP.get((item, t), 0)
        ok = "✓" if abs(total_alloc - cap_val) < 0.01 else "✗"
        print(f"     └─ [C4] SUM(q*CP+r)={total_alloc:.0f} == CAP={cap_val:.0f} {ok}")

    print(f"\n  TOTAL OBJECTIVE COST: {total_cost:.2f}")

    # ---- KIỂM TRA RÀNG BUỘC BALANCE ----
    print(f"\n{'─'*40}")
    print("KIỂM TRA INVENTORY BALANCE (C1-C3)")
    print(f"{'─'*40}")
    for j in j_list:
        bi_val = BI.get((item,j), 0)
        prev_I = None
        for ki, t in enumerate(T):
            qv = int(round(safe(q_v[(item,j,t)])))
            rv = int(round(safe(r_v[(item,j,t)])))
            cp = max(1, int(CP_param.get((item,j),1)))
            iv = safe(Iv[(item,j,t)])
            di = DI.get((item,j,t), 0)
            if ki == 0:
                expected = bi_val + di + qv*cp + rv
                src = f"BI({bi_val:.0f})+DI({di:.0f})+q({qv})*CP({cp})+r({rv})"
            else:
                expected = prev_I + di + qv*cp + rv
                src = f"I_prev({prev_I:.1f})+DI({di:.0f})+q({qv})*CP({cp})+r({rv})"
            ok = "✓" if abs(iv - expected) < 0.01 else f"✗ (got {iv:.1f})"
            print(f"  WH={j} T={t}: {src} = {expected:.1f} {ok}")
            prev_I = iv

if __name__ == "__main__":
    base = Path(__file__).parent
    cases = sorted([d for d in base.iterdir() if d.is_dir() and d.name.startswith("case")])

    if not cases:
        print("Không tìm thấy case nào. Chạy create_tests.py trước.")
        sys.exit(1)

    for case_dir in cases:
        run_case(case_dir)

    print(f"\n{SEPARATOR}")
    print("  HOÀN THÀNH TẤT CẢ TEST CASES")
    print(SEPARATOR)
