import warnings
warnings.filterwarnings("ignore")

import os
import sys
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base_dir)

import cvxpy as cp
import numpy as np
import pandas as pd

# from make_ieee30_uc_opf_es import ieee30_uc_opf_es_dict
# from make_PTDF_es import PTDF
#
# from run_uc import uc
#
# import opf_lmp_carbon
# from run_es import optimize_ess_schedule

def uc_es(sceneid, T, TG_offer, TG_maxG, TG_minG, TG_ramp, T_on, T_off, RG_offer, RG_P, RG_cap,
          RG_ramp, D_P, branch_max, PTDF, A_TG, A_RG, A_D, A_ES, ES_ramp, ES_P, eff, penalty_charge_matrix, bid_discharge_matrix):
    """
    带储能的机组组合优化，加入启停时间和其他约束，基于MOSEK求解。
    """
    AC = 1e3  # 定义惩罚系数，用于弃负荷
    AG = 1e2  # 弃低于最小火电出力的功率

    # 定义变量
    PG = cp.Variable((T, len(TG_maxG)))  # 煤机机组功率
    APG = cp.Variable((T, len(TG_maxG)))  # 煤机机组弃功率
    RG = cp.Variable((T, len(RG_P)))  # 可再生能源功率
    LS = cp.Variable((T, len(D_P[0])))  # 弃负荷
    s = cp.Variable((T, len(ES_ramp)))  # 储能功率（正为充电，负为放电）
    e = cp.Variable((T, len(ES_P)))  # 储能状态
    u = cp.Variable((T, len(TG_maxG)), boolean=True)  # 机组启停状态变量
    y = cp.Variable((T, len(TG_maxG)), boolean=True)  # 启动变量
    z = cp.Variable((T, len(TG_maxG)), boolean=True)  # 停机变量

    PD = D_P - LS

    TG_cost = cp.sum(cp.multiply(np.reshape(TG_offer, (1, len(TG_offer))), PG - APG)) + AG * cp.sum(APG)
    RG_cost = cp.sum(cp.multiply(np.reshape(RG_offer, (1, len(RG_offer))), RG))
    p_charge = cp.Variable((T, len(ES_P)))
    p_discharge = cp.Variable((T, len(ES_P)))
    ES_charge_penalty = -cp.sum(cp.multiply(penalty_charge_matrix, p_charge))
    ES_discharge_cost = cp.sum(cp.multiply(bid_discharge_matrix, p_discharge))
    PD_penalty = AC * cp.sum(LS)
    obj = TG_cost + RG_cost + ES_discharge_cost + PD_penalty + ES_charge_penalty

    cons = []

    for t in range(T):
        cons += [0 <= PD[t, :]]
        cons += [PD[t, :] <= D_P[t, :]]

        cons += [cp.multiply(u[t, :], TG_minG) <= PG[t, :]]
        cons += [PG[t, :] <= cp.multiply(u[t, :], TG_maxG)]
        cons += [0 <= APG[t, :]]
        cons += [APG[t, :] <= PG[t, :]]
        cons += [APG[t, :] <= TG_minG]

        for i in range(len(TG_maxG)):
            T_on_i = int(T_on[i])
            T_off_i = int(T_off[i])
            if t + 1 >= T_on_i:
                cons += [cp.sum(y[t - T_on_i + 1 : t + 1, i]) <= u[t, i]]
            else:
                cons += [cp.sum(y[:t + 1, i]) <= u[t, i]]
            if t + 1 >= T_off_i:
                cons += [cp.sum(z[t - T_off_i + 1 : t + 1, i]) <= 1 - u[t, i]]
            else:
                cons += [cp.sum(z[:t + 1, i]) <= 1 - u[t, i]]

        if t > 0:
            cons += [y[t, :] - z[t, :] == u[t, :] - u[t - 1, :]]
            cons += [cp.abs(PG[t, :] - PG[t - 1, :]) <= TG_ramp]

        cons += [0 <= RG[t, :]]
        # RG_cap assumed to be provided in global or as argument
        cons += [RG[t, :] <= cp.multiply(RG_cap[t, :], RG_P)]
        if t > 0:
            cons += [cp.abs(RG[t, :] - RG[t - 1, :]) <= RG_ramp]

        cons += [cp.abs(s[t, :]) <= ES_ramp]
        cons += [p_charge[t, :] >= 0]
        cons += [p_discharge[t, :] >= 0]
        cons += [s[t, :] == p_charge[t, :] - p_discharge[t, :]]

        b_charge = cp.Variable((len(ES_P)), boolean=True)
        cons += [p_charge[t, :] <= cp.multiply(ES_ramp, b_charge[:])]
        cons += [p_discharge[t, :] <= cp.multiply(ES_ramp, 1 - b_charge[:])]

        cons += [0 <= e[t, :]]
        cons += [e[t, :] <= ES_P]
        if t > 0:
            cons += [e[t, :] == e[t - 1, :] + cp.multiply(eff, p_charge[t - 1, :]) - cp.multiply(1 / eff, p_discharge[t - 1, :])]
        if t == 0 or t == T - 1:
            cons += [e[t, :] == 0.5 * ES_P]
        cons += [e[T - 1, :] + cp.multiply(eff, p_charge[T - 1, :]) - cp.multiply(1 / eff, p_discharge[T - 1, :]) == 0.5 * ES_P]

        cons += [cp.sum(PG[t, :] - APG[t, :]) + cp.sum(RG[t, :]) + cp.sum(p_discharge[t, :]) == cp.sum(PD[t, :]) + cp.sum(p_charge[t, :])]

        flow = (
            PTDF @ A_TG @ cp.reshape(PG[t, :] - APG[t, :], (-1, 1)) +
            PTDF @ A_RG @ cp.reshape(RG[t, :], (-1, 1)) +
            PTDF @ A_D @ (-cp.reshape(D_P[t, :], (-1, 1))) +
            PTDF @ A_ES @ (-cp.reshape(s[t, :], (-1, 1)))
        )
        cons += [flow <= cp.reshape(branch_max, (-1, 1))]
        cons += [flow >= -cp.reshape(branch_max, (-1, 1))]

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
    else:
        print("⚠️ 优化器未返回可行解（u.value 为 None）。可能是模型不可行或未收敛。")
        return None

    result = {
        "u": u_value_clipped,
        "PG": PG.value,
        "APG": APG.value,
        "RG": RG.value,
        "PD": PD.value,
        "LS": LS.value,
        "s": s.value,
        "e": e.value,
    }

    # 保存结果到 results 文件夹
    output_dir = os.path.join(base_dir, 'results')
    os.makedirs(output_dir, exist_ok=True)

    # 保存文件
    output_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(__file__))[0]}_result_{sceneid}.xlsx")
    print(f"已将含储能机组组合结果保存到 '{os.path.splitext(os.path.basename(__file__))[0]}_result_{sceneid}.xlsx'")
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        pd.DataFrame(result["u"]).to_excel(writer, sheet_name="u (启停状态)", index=False)
        pd.DataFrame(result["PG"]).to_excel(writer, sheet_name="PG (功率输出)", index=False)
        pd.DataFrame(result["APG"]).to_excel(writer, sheet_name="APG (弃功率)", index=False)
        pd.DataFrame(result["RG"]).to_excel(writer, sheet_name="RG (可再生)", index=False)
        pd.DataFrame(result["PD"]).to_excel(writer, sheet_name="PD (负荷需求)", index=False)
        pd.DataFrame(result["LS"]).to_excel(writer, sheet_name="LS (弃负荷)", index=False)
        pd.DataFrame(result["s"]).to_excel(writer, sheet_name="s (储能功率)", index=False)
        pd.DataFrame(result["e"]).to_excel(writer, sheet_name="e (储能状态)", index=False)

    return result

# if __name__ == "__main__":
#     try:
#         sceneid = 20
#         case_example = ieee30_uc_opf_es_dict(sceneid)
#
#         # 提取参数
#         T = case_example['T']
#         TG_offer = case_example['TG_offer'].astype(float)
#         TG_carbon = case_example['TG_carbon'].astype(float)
#         TG_maxG = case_example['TG_maxG'].astype(float)
#         TG_minG = case_example['TG_minG'].astype(float)
#         TG_ramp = case_example['TG_ramp'].astype(float)
#         T_on = case_example['T_on']
#         T_off = case_example['T_off']
#         RG_offer = case_example['RG_offer'].astype(float)
#         RG_P = case_example['RG_P'].astype(float)
#         RG_ramp = case_example['RG_ramp'].astype(float)
#         RG_cap = case_example['RG_cap'].astype(float)
#         D_P = case_example['D_P'].astype(float)
#         # 储能相关参数
#         ES_ramp = case_example['ES_ramp'].astype(float)
#         ES_P = case_example['ES_P'].astype(float)
#         eff = case_example['eff'].astype(float)
#
#         # 调用 PTDF 函数
#         PTDF_result = PTDF(case_example)
#
#         PTDF = PTDF_result['PTDF']
#         branch_max = PTDF_result['branch_max']
#         A_TG = PTDF_result['A_TG']
#         A_RG = PTDF_result['A_RG']
#         A_D = PTDF_result['A_D']
#         A_ES = PTDF_result['A_ES']
#
#         u = uc(T, TG_offer, TG_maxG, TG_minG, TG_ramp, T_on, T_off, RG_offer, RG_P, RG_cap,
#                RG_ramp, D_P, branch_max, PTDF, A_TG, A_RG, A_D)['u']
#
#         result = uc(T, TG_offer, TG_maxG, TG_minG, TG_ramp, T_on, T_off, RG_offer, RG_P, RG_cap,
#                     RG_ramp, D_P, branch_max, PTDF, A_TG, A_RG, A_D)
#         print(result)
#
#         LMP_matrix = opf_lmp_carbon.run_opf_carbon(T, u, TG_carbon, TG_offer, TG_maxG, TG_minG,
#                                     RG_offer, RG_P, RG_cap, D_P, branch_max, PTDF, A_TG, A_RG, A_D)['LMP']
#
#         prices = (LMP_matrix @ A_ES).T
#         print(prices)
#
#         ess_result = optimize_ess_schedule(T, prices, sceneid)
#
#         # 储能报价矩阵
#         penalty_charge_matrix = ess_result['penalty_charge_matrix']
#         bid_discharge_matrix = ess_result['bid_discharge_matrix']
#         # print("储能充电未消纳惩罚系数\n", penalty_charge_matrix)
#         # print("储能放电报价\n", bid_discharge_matrix)
#
#         # 调用优化函数
#         result = uc_es(T, TG_offer, TG_maxG, TG_minG, TG_ramp, T_on, T_off, RG_offer, RG_P, RG_cap,
#                        RG_ramp, D_P, branch_max, PTDF, A_TG, A_RG, A_D, A_ES, ES_ramp, ES_P, eff, penalty_charge_matrix, bid_discharge_matrix)
#         if result:
#             # 输出结果
#             print("煤机机组启停状态:\n", result["u"])
#             print("传统机组功率输出:\n", result["PG"])
#             print("煤机机组弃功率：\n", result["APG"])
#             print("可再生能源功率输出:\n", result["RG"])
#             print("负荷:\n", result["PD"])
#             print("储能功率:\n", result["s"])
#             print("储能状态:\n", result["e"])
#     except Exception as e:
#         print(f"运行出错：{str(e)}")
