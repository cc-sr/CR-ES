import os
import sys
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir)

import cvxpy as cp
import pandas as pd

def opf_carbon(u_t, TG_carbon, TG_offer, TG_maxG, TG_minG, RG_offer, RG_P, RG_cap_t,
               D_P_t, branch_max, PTDF, A_TG, A_RG, A_D):
    """进行每小时的 OPF 运算，返回每小时的碳排放和节点边际电价(LMP)"""
    AC = 5e3  # 弃负荷惩罚系数
    AG = 2e2  # 弃低于最小火电出力的功率
    AR = 1e2  # 弃新能源功率

    # 定义变量
    PG = cp.Variable(len(TG_maxG))  # 传统机组出力
    APG = cp.Variable(len(TG_maxG))  # 传统机组弃功率
    RG = cp.Variable(len(RG_P))  # 可再生能源出力
    LS = cp.Variable(len(D_P_t))  # 弃负荷
    PD = D_P_t - LS

    renewable_available = RG_cap_t * RG_P
    # 目标函数
    TG_cost = cp.sum(cp.multiply(TG_offer, (PG - APG))) + AG * cp.sum(APG)
    RG_cost = cp.sum(cp.multiply(RG_offer, RG))

    obj = TG_cost + RG_cost + AR * cp.sum(renewable_available - RG) + AC * cp.sum(LS)

    # 约束条件
    constraints = [
        # 功率平衡
        cp.sum(PG - APG) + cp.sum(RG) == cp.sum(PD),
        # 线路潮流约束
        PTDF @ (A_TG @ (PG - APG) + A_RG @ RG - A_D @ PD) <= branch_max,
        PTDF @ (A_TG @ (PG - APG) + A_RG @ RG - A_D @ PD) >= -branch_max,
        # 传统机组约束
        TG_minG * u_t <= PG, PG <= TG_maxG * u_t,
        # 可再生能源约束
        0 <= RG, RG <= renewable_available,
        # 弃负荷约束
        0 <= LS, LS <= D_P_t,
        # 弃功率约束
        0 <= APG, APG <= PG
    ]

    # 求解优化问题
    prob = cp.Problem(cp.Minimize(obj), constraints)
    try:
        prob.solve(
            solver=cp.MOSEK,
            mosek_params={
                'MSK_IPAR_NUM_THREADS': 2,
            },
            verbose=False
        )
    except cp.error.SolverError:
        try:
            prob.solve(
                solver=cp.MOSEK,
                mosek_params={
                    "MSK_IPAR_NUM_THREADS": 2,
                    "MSK_DPAR_INTPNT_TOL_REL_GAP": 1e-4,
                    "MSK_DPAR_INTPNT_TOL_PFEAS": 1e-4,
                    "MSK_DPAR_INTPNT_TOL_DFEAS": 1e-4,
                },
                verbose=False
            )
        except cp.error.SolverError:
            print("Solver MOSEK failed. Trying verbose mode for diagnostics.")
            prob.solve(
                solver=cp.MOSEK,
                mosek_params={
                    "MSK_IPAR_NUM_THREADS": 2,
                    "MSK_DPAR_INTPNT_TOL_REL_GAP": 1e-4,
                    "MSK_DPAR_INTPNT_TOL_PFEAS": 1e-4,
                    "MSK_DPAR_INTPNT_TOL_DFEAS": 1e-4,
                },
                verbose=True
            )

    # prob.solve(
    #     solver=cp.GUROBI,
    #     Threads=2,
    #     MipGap=0.0,
    #     verbose=False
    # )

    if prob.status == cp.OPTIMAL:

        carbon_t = TG_carbon @ PG.value
        # print(f'carbon_t={carbon_t}t-CO2')

        return {
            "carbon_t": carbon_t,
            "status": prob.status,
            # "PG": PG.value,
            # "APG": APG.value,
            # "RG": RG.value
        }

    else:
        return {
            "carbon_t": 0,
            "status": prob.status,
            # "PG": None,
            # "APG": None,
            # "RG": None
        }


def run_opf_carbon(T, u, TG_carbon, TG_offer, TG_maxG, TG_minG,
                   RG_offer, RG_P, RG_cap, D_P, branch_max, PTDF, A_TG, A_RG, A_D):
    # 初始化结果存储
    carbon = 0
    carbon_list = []

    for t in range(T):
        # print(f"时段 {t + 1}:")
        # 获取当前时段参数
        u_t = u[t]
        D_P_t = D_P[t, :]
        RG_cap_t = RG_cap[t, :]

        # 求解OPF
        opf_result = opf_carbon(u_t, TG_carbon, TG_offer,
                                TG_maxG, TG_minG, RG_offer, RG_P, RG_cap_t,
                                D_P_t, branch_max, PTDF, A_TG, A_RG, A_D)

        if opf_result['status'] == cp.OPTIMAL:
            # print(f"t={t},carbon_{t}={opf_result['carbon_t']}t_CO2")
            carbon += opf_result['carbon_t']
            carbon_list.append(opf_result['carbon_t'])
        else:
            print("OPF求解失败")
            carbon_list.append(None)  # 失败时填空

    # 保存结果到 Excel
    output_dir = os.path.join(os.path.dirname(__file__), 'results')  # 获取当前文件夹下的results文件夹
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_path = os.path.join(output_dir, "opf_carbon_result.xlsx")  # 保存路径
    if os.path.exists(output_path):
        old_df = pd.read_excel(output_path, sheet_name="Sheet1")
        while len(carbon_list) < T:
            carbon_list.append(None)
        old_df["carbon_es"] = carbon_list + [carbon]
        old_df.to_excel(output_path, sheet_name="Sheet1", index=False)
    else:
        df_result = pd.DataFrame({
            "hour": list(range(T)) + ["total"],
            "placeholder": [None] * T + [None],
            "carbon_es": carbon_list + [carbon]
        })
        df_result.to_excel(output_path, sheet_name="Sheet1", index=False)

    return {
        "carbon": carbon
    }
