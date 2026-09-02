import os
import sys
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir)

import cvxpy as cp
import numpy as np
import pandas as pd

def opf_carbon(u_t, TG_Carbon, TG_offer, TG_maxG, TG_minG, RG_offer, RG_P, RG_cap_t,
               D_P_t, branch_max, PTDF, A_TG, A_RG, A_D):
    """进行每小时的 OPF 运算，返回每小时的碳排放和节点边际电价(LMP)"""
    AC = float(5e3)  # 弃负荷惩罚系数
    AG = float(2e2)  # 弃低于最小火电出力的功率
    AR = float(1e2)  # 弃新能源功率

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
        # 获取对偶变量
        lambda_p = constraints[0].dual_value  # 功率平衡对偶变量
        mu_min = constraints[1].dual_value  # 潮流上界对偶变量
        mu_max = constraints[2].dual_value  # 潮流下界对偶变量

        # 计算LMP = -λ + PTDF^T @ (μ_min - μ_max)
        congestion = mu_min - mu_max
        LMP = -lambda_p + PTDF.T @ congestion

        # print("lambda_p:", -lambda_p)
        # print("congestion:", congestion)

        carbon_t = TG_Carbon @ PG.value
        # print(f'carbon_t={carbon_t}t_CO2')

        return {
            "carbon_t": carbon_t,
            "LMP": LMP,
            "status": prob.status,
            "PG": PG.value,
            "APG": APG.value,
            "RG": RG.value
        }

    else:
        return {
            "carbon_t": 0,
            "LMP": None,
            "status": prob.status,
            "PG": None,
            "APG": None,
            "RG": None
        }


def run_opf_carbon(sceneid, T, u, TG_carbon, TG_offer, TG_maxG, TG_minG,
                   RG_offer, RG_P, RG_cap, D_P, branch_max, PTDF, A_TG, A_RG, A_D, D_num):
    num_buses = PTDF.shape[1]  # 获取节点数量

    # 初始化结果存储
    carbon = 0
    LMPs = np.full((T, num_buses), float('nan'))  # T小时×节点数

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
            LMPs[t, :] = opf_result['LMP']
            carbon_list.append(opf_result['carbon_t'])
        else:
            print("OPF求解失败")
            carbon_list.append(None)  # 失败时填空

    # 保存结果到 Excel
    # 获取当前文件夹路径
    output_dir = os.path.join(base_dir, 'results')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(__file__))[0]}_result_{sceneid}_D_{D_num}.xlsx")
    print(f"已将节点电价结果保存到 '{os.path.splitext(os.path.basename(__file__))[0]}_result_{sceneid}_D_{D_num}.xlsx'")

    df_carbon = pd.DataFrame({
        "hour": list(range(T)),
        "carbon_t": carbon_list
    })
    df_carbon.loc[T] = ["total", carbon]

    # 构造 df_lmp
    df_lmp = pd.DataFrame(
        LMPs,
        columns=[f'Bus_{i}' for i in range(num_buses)]
    )
    df_lmp.insert(0, "hour", list(range(T)))

    # 写入 Excel 的不同 Sheet
    with pd.ExcelWriter(output_path, engine='openpyxl', mode='w') as writer:
        df_carbon.to_excel(writer, index=False, sheet_name='carbon')
        df_lmp.to_excel(writer, index=False, sheet_name='LMPs')

    return {
        "carbon": carbon,
        "LMP": LMPs
    }
