"""
oa_plt_milp.py  —  OA + PLT Combined MILP Model
================================================
Implements the updated formulation requested by the user.
"""

import os

from pulp import (
    LpProblem, LpMinimize, LpVariable, LpStatus, lpSum,
    PULP_CBC_CMD, value
)


class OA_PLT_Model:
    """Combined OA + PLT MILP model."""

    def __init__(self, params: dict):
        self.params = params
        self.P = [params["meta"]["product"]]
        self.N = params["meta"]["warehouses"]
        self.T = params["meta"]["T"]
        self.periods = list(range(1, self.T + 1))
        self.prob = None
        self._vars = {}

    def _key(self, wh, t):
        return f"{wh}_{t}"

    def _dI(self, p, i, t):
        return self.params["delta_I"].get(self._key(i, t), 0)

    def _U(self, p, i, t):
        return self.params["U"].get(self._key(i, t), 1e6)

    def _L(self, p, i, t):
        return self.params["L"].get(self._key(i, t), 0)

    def _CAP(self, p, t):
        return self.params["CAP"].get(str(t), 0)

    def _cost(self, wh, t, kind):
        return self.params["cost"].get(wh, {}).get(str(t), {}).get(kind, 0.0)

    def _d(self, wi, wj):
        return self.params["distance"].get(f"{wi}_{wj}", 0)

    def _CP(self, p, wh, t):
        cp = self.params["CP"]
        if isinstance(cp, dict):
            return cp.get(
                f"{p}_{wh}_{t}",
                cp.get(f"{wh}_{t}", cp.get(wh, cp.get(str(t), 1)))
            )
        return cp

    def _OA_lead(self, i):
        oa_lead = self.params.get("OA_lead", 8)
        if isinstance(oa_lead, dict):
            return oa_lead.get(i, oa_lead.get(str(i), 8))
        return oa_lead

    def _PLT_lead(self, wi, wj):
        return self.params["PLT_lead"].get(f"{wi}_{wj}", 2)

    def build(self):
        P, N, T_list = self.P, self.N, self.periods
        periods_0 = list(range(0, self.T + 1))
        TC = self.params["TC"]

        prob = LpProblem("OA_PLT_Combined", LpMinimize)

        q_OA = LpVariable.dicts("qOA", (P, N, T_list), lowBound=0, cat="Integer")
        r_OA = LpVariable.dicts("rOA", (P, N, T_list), lowBound=0, cat="Integer")
        Q_OA = LpVariable.dicts("QOA", (P, N, T_list), lowBound=0, cat="Integer")

        q_PLT = LpVariable.dicts("qPLT", (P, N, N, T_list), lowBound=0, cat="Integer")
        r_PLT = LpVariable.dicts("rPLT", (P, N, N, T_list), lowBound=0, cat="Integer")
        Q_PLT = LpVariable.dicts("QPLT", (P, N, N, T_list), lowBound=0, cat="Integer")

        I_var = LpVariable.dicts("I", (P, N, periods_0), cat="Continuous")
        bo = LpVariable.dicts("bo", (P, N, T_list), lowBound=0)
        o = LpVariable.dicts("o", (P, N, T_list), lowBound=0)
        s = LpVariable.dicts("s", (P, N, T_list), lowBound=0)
        E = LpVariable.dicts("E", (P, N, T_list), lowBound=0)

        pOA = LpVariable.dicts("pOA", (P, N, T_list), cat="Binary")
        pPLT = LpVariable.dicts("pPLT", (P, N, N, T_list), cat="Binary")
        x = LpVariable.dicts("x", (N, N, T_list), cat="Binary")

        obj_terms = []
        for p in P:
            for i in N:
                for t in T_list:
                    obj_terms.append(self._cost(i, t, "overstock") * o[p][i][t])
                    obj_terms.append(self._cost(i, t, "shortage") * s[p][i][t])
                    obj_terms.append(self._cost(i, t, "backorder") * bo[p][i][t])
                    obj_terms.append(self._cost(i, t, "penalty") * pOA[p][i][t])
                    for j in N:
                        if i != j:
                            obj_terms.append(self._cost(j, t, "penalty") * pPLT[p][i][j][t])
                            obj_terms.append(self._d(i, j) * TC * x[i][j][t])
        prob += lpSum(obj_terms), "Objective"

        BI_map = self.params["BI"]
        M = max(self._U(p, i, t) for p in P for i in N for t in T_list)

        for p in P:
            for i in N:
                prob += (I_var[p][i][0] == BI_map[i], f"Init_Inv_{p}_{i}")

        for p in P:
            for i in N:
                for t in T_list:
                    cp = self._CP(p, i, t)
                    prob += (Q_OA[p][i][t] == q_OA[p][i][t] * cp + r_OA[p][i][t], f"QOA_def_{p}_{i}_{t}")

        for p in P:
            for i in N:
                for j in N:
                    if i == j:
                        continue
                    for t in T_list:
                        cp_j = self._CP(p, j, t)
                        prob += (Q_PLT[p][i][j][t] == q_PLT[p][i][j][t] * cp_j + r_PLT[p][i][j][t], f"QPLT_def_{p}_{i}_{j}_{t}")

        for p in P:
            for i in N:
                for t in T_list:
                    oa_lead_i = self._OA_lead(i)
                    t_oa = t - oa_lead_i
                    oa_in = Q_OA[p][i][t_oa] if 1 <= t_oa <= self.T else 0

                    plt_in = []
                    for j in N:
                        if j == i:
                            continue
                        lt = self._PLT_lead(j, i)
                        t_plt = t - lt
                        if 1 <= t_plt <= self.T:
                            plt_in.append(Q_PLT[p][j][i][t_plt])

                    plt_out = [Q_PLT[p][i][j][t] for j in N if j != i]

                    prob += (
                        I_var[p][i][t] == I_var[p][i][t - 1] + oa_in + lpSum(plt_in) - lpSum(plt_out) + self._dI(p, i, t),
                        f"Inv_balance_{p}_{i}_{t}"
                    )

        for p in P:
            for t in T_list:
                prob += (lpSum(Q_OA[p][i][t] for i in N) == self._CAP(p, t), f"Capacity_{p}_{t}")

        for p in P:
            for i in N:
                for t in T_list:
                    prob += (bo[p][i][t] >= -I_var[p][i][t], f"bo_def_{p}_{i}_{t}")
                    prob += (o[p][i][t] >= I_var[p][i][t] - self._U(p, i, t), f"o_def_{p}_{i}_{t}")
                    prob += (s[p][i][t] >= self._L(p, i, t) - I_var[p][i][t], f"s_def_{p}_{i}_{t}")
                    prob += (E[p][i][t] >= I_var[p][i][t] - self._L(p, i, t), f"E_def_{p}_{i}_{t}")
                    prob += (
                        lpSum(Q_PLT[p][i][j][t] for j in N if j != i) <= E[p][i][t],
                        f"PLT_surplus_{p}_{i}_{t}"
                    )

        for p in P:
            for i in N:
                for t in T_list:
                    cp = self._CP(p, i, t)
                    prob += (r_OA[p][i][t] <= cp - 1, f"rOA_ub_{p}_{i}_{t}")
                    prob += (r_OA[p][i][t] <= M * pOA[p][i][t], f"rOA_bigM_{p}_{i}_{t}")
                    prob += (r_OA[p][i][t] >= pOA[p][i][t], f"rOA_lb_{p}_{i}_{t}")

        for p in P:
            for i in N:
                oa_lead_i = self._OA_lead(i)
                for j in N:
                    if i == j:
                        continue
                    for t in T_list:
                        if t <= oa_lead_i - 1:
                            cp_j = self._CP(p, j, t)
                            prob += (r_PLT[p][i][j][t] <= cp_j - 1, f"rPLT_ub_{p}_{i}_{j}_{t}")
                            prob += (Q_PLT[p][i][j][t] <= M * x[i][j][t], f"PLT_bigM_{p}_{i}_{j}_{t}")
                            prob += (r_PLT[p][i][j][t] <= M * pPLT[p][i][j][t], f"rPLT_bigM_{p}_{i}_{j}_{t}")
                            prob += (r_PLT[p][i][j][t] >= pPLT[p][i][j][t], f"rPLT_lb_{p}_{i}_{j}_{t}")


        for i in N:
            for t in T_list:
                prob += (x[i][i][t] == 0, f"x_diag_{i}_{t}")

        self.prob = prob
        self._vars = {
            "q_OA": {(p, i, t): q_OA[p][i][t] for p in P for i in N for t in T_list},
            "r_OA": {(p, i, t): r_OA[p][i][t] for p in P for i in N for t in T_list},
            "Q_OA": {(p, i, t): Q_OA[p][i][t] for p in P for i in N for t in T_list},
            "q_PLT": {(p, i, j, t): q_PLT[p][i][j][t] for p in P for i in N for j in N if i != j for t in T_list},
            "r_PLT": {(p, i, j, t): r_PLT[p][i][j][t] for p in P for i in N for j in N if i != j for t in T_list},
            "Q_PLT": {(p, i, j, t): Q_PLT[p][i][j][t] for p in P for i in N for j in N if i != j for t in T_list},
            "I": {(p, i, t): I_var[p][i][t] for p in P for i in N for t in T_list},
            "bo": {(p, i, t): bo[p][i][t] for p in P for i in N for t in T_list},
            "o": {(p, i, t): o[p][i][t] for p in P for i in N for t in T_list},
            "s": {(p, i, t): s[p][i][t] for p in P for i in N for t in T_list},
            "E": {(p, i, t): E[p][i][t] for p in P for i in N for t in T_list},
            "pOA": {(p, i, t): pOA[p][i][t] for p in P for i in N for t in T_list},
            "pPLT": {(p, i, j, t): pPLT[p][i][j][t] for p in P for i in N for j in N if i != j for t in T_list},
            "x": {(i, j, t): x[i][j][t] for i in N for j in N for t in T_list},
        }
        return self

    def solve(self, time_limit: int = 300, msg: int = 1) -> str:
        if self.prob is None:
            self.build()
        solver = PULP_CBC_CMD(msg=msg, timeLimit=time_limit)
        self.prob.solve(solver)
        status = LpStatus[self.prob.status]
        print(f"  Solver status: {status}")
        print(f"  Objective    : {value(self.prob.objective):,.2f}")
        return status

    def get_results(self) -> dict:
        P, N, T_list = self.P, self.N, self.periods

        def v(var_dict, key, default=0.0):
            var = var_dict.get(key)
            if var is None:
                return default
            val = value(var)
            return val if val is not None else default

        results = {
            "objective": value(self.prob.objective),
            "status": LpStatus[self.prob.status],
            "I": {},
            "Q_OA": {},
            "q_OA": {},
            "r_OA": {},
            "Q_PLT": {},
            "q_PLT": {},
            "r_PLT": {},
            "bo": {},
            "o": {},
            "s": {},
            "E": {},
            "pOA": {},
            "pPLT": {},
            "x": {},
        }

        vI = self._vars["I"]
        vQOA = self._vars["Q_OA"]
        vqOA = self._vars["q_OA"]
        vrOA = self._vars["r_OA"]
        vQPLT = self._vars["Q_PLT"]
        vqPLT = self._vars["q_PLT"]
        vrPLT = self._vars["r_PLT"]
        vbo = self._vars["bo"]
        vo = self._vars["o"]
        vs = self._vars["s"]
        vE = self._vars["E"]
        vpOA = self._vars["pOA"]
        vpPLT = self._vars["pPLT"]
        vx = self._vars["x"]

        for p in P:
            for i in N:
                for t in T_list:
                    k = f"{i}_t{t}"
                    inv_val = v(vI, (p, i, t))
                    results["I"][k] = round(inv_val, 2)
                    results["Q_OA"][k] = round(v(vQOA, (p, i, t)), 0)
                    results["q_OA"][k] = round(v(vqOA, (p, i, t)), 0)
                    results["r_OA"][k] = round(v(vrOA, (p, i, t)), 0)
                    results["bo"][k] = round(v(vbo, (p, i, t)), 2)
                    results["o"][k] = round(v(vo, (p, i, t)), 2)
                    results["s"][k] = round(v(vs, (p, i, t)), 2)
                    results["E"][k] = round(v(vE, (p, i, t)), 2)
                    results["pOA"][k] = round(v(vpOA, (p, i, t)), 0)

                    for j in N:
                        if i == j:
                            continue
                        kp = f"{i}_{j}_t{t}"
                        results["Q_PLT"][kp] = round(v(vQPLT, (p, i, j, t)), 0)
                        results["q_PLT"][kp] = round(v(vqPLT, (p, i, j, t)), 0)
                        results["r_PLT"][kp] = round(v(vrPLT, (p, i, j, t)), 0)
                        results["pPLT"][kp] = round(v(vpPLT, (p, i, j, t)), 0)
                        results["x"][kp] = round(v(vx, (i, j, t)), 0)

        return results