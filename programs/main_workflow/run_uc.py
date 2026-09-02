import os
import sys
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir)

import cvxpy as cp
import numpy as np
import pandas as pd

def uc(sceneid, T, TG_offer, TG_maxG, TG_minG, TG_ramp, T_on, T_off, RG_offer, RG_P, RG_cap,
       RG_ramp, D_P, branch_max, PTDF, A_TG, A_RG, A_D,
       TG_start_cost=None, TG_stop_cost=None, initial_u=None):
    """
    带储能的机组组合优化，加入启停时间和其他约束，基于MOSEK求解。
    """
    AC = 5e3  # 定义惩罚系数，用于弃负荷
    AG = 2e2  # 弃低于最小火电出力的功率
    AR = 1e2  # 弃新能源功率

    # 定义变量
    PG = cp.Variable((T, len(TG_maxG)))  # 煤机机组功率
    APG = cp.Variable((T, len(TG_maxG)))  # 煤机机组弃功率
    RG = cp.Variable((T, len(RG_P)))  # 可再生能源功率
    LS = cp.Variable((T, len(D_P[0])))  # 弃负荷
    u = cp.Variable((T, len(TG_maxG)), boolean=True)  # 机组启停状态变量
    y = cp.Variable((T, len(TG_maxG)), boolean=True)  # 启动变量
    z = cp.Variable((T, len(TG_maxG)), boolean=True)  # 停机变量

    PD = D_P - LS
    if TG_start_cost is None:
        TG_start_cost = np.zeros(len(TG_maxG))
    if TG_stop_cost is None:
        TG_stop_cost = np.zeros(len(TG_maxG))
    TG_start_cost = np.asarray(TG_start_cost, dtype=float)
    TG_stop_cost = np.asarray(TG_stop_cost, dtype=float)

    TG_cost = cp.sum(cp.multiply(np.reshape(TG_offer, (1, len(TG_offer))), PG - APG)) + AG * cp.sum(APG)
    if T > 1:
        TG_commit_cost = (
            cp.sum(cp.multiply(np.reshape(TG_start_cost, (1, len(TG_start_cost))), y[1:, :])) +
            cp.sum(cp.multiply(np.reshape(TG_stop_cost, (1, len(TG_stop_cost))), z[1:, :]))
        )
    else:
        TG_commit_cost = 0
    renewable_available = RG_cap * np.reshape(RG_P, (1, len(RG_P)))
    # 可再生能源成本
    RG_cost = cp.sum(cp.multiply(cp.reshape(RG_offer, (1, len(RG_offer))), RG))
    RG_curtailment_cost = AR * cp.sum(renewable_available - RG)

    # 目标函数
    obj = TG_cost + TG_commit_cost + RG_cost + RG_curtailment_cost + AC * cp.sum(LS)

    # 约束条件
    cons = []
    if initial_u is not None:
        initial_u = np.asarray(initial_u, dtype=float)
        cons += [
            y[0, :] - z[0, :] == u[0, :] - initial_u,
            y[0, :] <= 1 - initial_u,
            z[0, :] <= initial_u,
        ]

    for t in range(T):
        # 负荷功率约束
        cons += [0 <= PD[t, :], PD[t, :] <= D_P[t, :]]
        # 传统机组功率约束
        cons += [
            cp.multiply(u[t, :], TG_minG) <= PG[t, :], PG[t, :] <= cp.multiply(u[t, :], TG_maxG),  # 输出功率范围
            0 <= APG[t, :], APG[t, :] <= PG[t, :], APG[t, :] <= TG_minG  # 弃功率范围
        ]
        # 最小启停时间约束
        for i in range(len(TG_maxG)):
            T_on_i = int(T_on[i])
            T_off_i = int(T_off[i])
            if t + 1 >= T_on_i:
                cons += [cp.sum(y[t - T_on_i + 1:t + 1, i]) <= u[t, i]]
            else:
                cons += [cp.sum(y[:t + 1, i]) <= u[t, i]]
            if t + 1 >= T_off_i:
                cons += [cp.sum(z[t - T_off_i + 1:t + 1, i]) <= 1 - u[t, i]]
            else:
                cons += [cp.sum(z[:t + 1, i]) <= 1 - u[t, i]]

        if t > 0:
            # 机组启停逻辑
            cons += [y[t, :] - z[t, :] == u[t, :] - u[t - 1, :]]
            # 爬坡速率约束
            cons += [cp.abs(PG[t, i] - PG[t - 1, i]) <= TG_ramp[i] for i in range(len(TG_maxG))]

        # 新能源机组功率约束
        cons += [0 <= RG[t, :], RG[t, :] <= renewable_available[t, :]]

        # 新能源爬坡速率约束
        if t > 0:
            cons += [cp.abs(RG[t, :] - RG[t - 1, :]) <= RG_ramp]

        # 功率平衡约束
        cons += [cp.sum(PG[t, :] - APG[t, :]) + cp.sum(RG[t, :]) == cp.sum(PD[t, :])]

        # 潮流约束
        flow = (
                PTDF @ A_TG @ cp.reshape(PG[t, :] - APG[t, :], (-1, 1)) +
                PTDF @ A_RG @ cp.reshape(RG[t, :], (-1, 1)) +
                PTDF @ A_D @ (-cp.reshape(D_P[t, :], (-1, 1)))
        )
        cons += [
            flow <= cp.reshape(branch_max, (-1, 1)),
            flow >= -cp.reshape(branch_max, (-1, 1))
        ]

    # 优化问题
    prob = cp.Problem(cp.Minimize(obj), cons)
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

    if u.value is not None:
        u_value_rounded = np.round(u.value)
        u_value_rounded[u_value_rounded == -0] = 0
        u_value_clipped = np.clip(u_value_rounded, 0, 1)
        u_RG = np.array(u_value_clipped)
    else:
        print("⚠️ 优化器未返回可行解（u.value 为 None）。可能是模型不可行或未收敛。")
        return None

    result = {
        "PD": PD.value,
        "u": u_RG,
        "PG": PG.value,
        "LS": LS.value,
        "APG": APG.value,
        "RG": RG.value,
    }

    # 保存结果到 results 文件夹
    output_dir = os.path.join(base_dir, 'results')
    os.makedirs(output_dir, exist_ok=True)

    # 保存文件
    output_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(__file__))[0]}_result_{sceneid}.xlsx")
    print(f"已将原始机组组合结果保存到 '{os.path.splitext(os.path.basename(__file__))[0]}_result_{sceneid}.xlsx'")
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        pd.DataFrame(result["u"]).to_excel(writer, sheet_name="u (启停状态)", index=False)
        pd.DataFrame(result["PG"]).to_excel(writer, sheet_name="PG (功率输出)", index=False)
        pd.DataFrame(result["APG"]).to_excel(writer, sheet_name="APG (弃功率)", index=False)
        pd.DataFrame(result["RG"]).to_excel(writer, sheet_name="RG (可再生)", index=False)
        pd.DataFrame(result["PD"]).to_excel(writer, sheet_name="PD (负荷需求)", index=False)
        pd.DataFrame(result["LS"]).to_excel(writer, sheet_name="LS (弃负荷)", index=False)

    return result
