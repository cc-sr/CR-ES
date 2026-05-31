import warnings
warnings.filterwarnings("ignore")

import os
import sys
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir)

import numpy as np
import pandas as pd
import cvxpy as cp

from make_PTDF_es import PTDF
from run_uc import uc
from opf_lmp_carbon import run_opf_carbon

def optimize_ess_schedule(T, prices, sceneid, ES_num, ES_ramp, ES_P, eff, lambda_param=1000, epsilon=0.1):
    """
    储能系统优化调度函数
    :param prices: 每个储能对应的T小时电价序列集合，形状为 (num_ess, T)
    :param epsilon: 价格变化阈值，当价格差异小于此值时，储能不进行充放电
    :return: 包含两个储能运行曲线的字典（DataFrame格式）
    """
    ess_params = {}
    es_num = ES_num
    for i in range(es_num):
        ess_name = f'ESS{i+1}'
        ess_params[ess_name] = {
            'charge_max': ES_ramp[i],  # 最大充电功率
            'discharge_max': ES_ramp[i], # 最大放电功率
            'capacity': ES_P[i], # 储能容量
            'eff_charge': eff[i], # 充电效率
            'eff_discharge': eff[i], # 放电效率
            'soc_initial': ES_P[i] * 0.5  # 初始SOC设为50%
        }

    ess_variables = {}
    for ess in ess_params:
        ess_variables[ess] = {
            'charge': cp.Variable(T, nonneg=True),
            'discharge': cp.Variable(T, nonneg=True),
            'soc': cp.Variable(T, nonneg=True),
            'u': cp.Variable(T, boolean=True)
        }

    cons = []
    for ess in ess_params:
        params = ess_params[ess]
        var = ess_variables[ess]

        # 初始和终止SOC约束
        cons += [var['soc'][0] == params['soc_initial']]
        cons += [var['soc'][T-1] == params['soc_initial']]
        cons += [var['soc'][T-1] + var['charge'][T-1] * params['eff_charge'] -
                           var['discharge'][T-1] / params['eff_discharge'] == params['soc_initial']]

        # 充放电最大功率约束
        cons += [var['charge'] <= params['charge_max']]
        cons += [var['discharge'] <= params['discharge_max']]
        cons += [var['soc'] <= params['capacity']]

        # 充放电互斥约束
        for t in range(T):
            cons += [var['charge'][t] <= (1 - var['u'][t]) * params['charge_max']]
            cons += [var['discharge'][t] <= var['u'][t] * params['discharge_max']]

        for t in range(T-1):
            cons += [
                var['soc'][t+1] == var['soc'][t] +
                var['charge'][t] * params['eff_charge'] -
                var['discharge'][t] / params['eff_discharge']
            ]

        # 价格波动的惩罚项：当价格波动小于阈值时，惩罚充放电操作
        price_diff_penalty = 0
        for i, ess in enumerate(ess_params):
            var = ess_variables[ess]
            for t in range(1, T):
                # 计算价格变化
                price_change = cp.abs(prices[i, t] - prices[i, t - 1])
                # 当价格变化小于阈值 epsilon 时，增加充放电的惩罚
                penalty_weight = cp.maximum(0, epsilon - price_change)  # 如果价格变化小于 epsilon，惩罚充放电行为
                price_diff_penalty += cp.square(penalty_weight) * (var['charge'][t] + var['discharge'][t])

    # 目标函数：最大化利润并加入价格波动惩罚项
    objective = cp.Maximize(
        cp.sum([var['discharge'][t] * prices[i, t] - var['charge'][t] * prices[i, t]
                for i, ess in enumerate(ess_params) for var in [ess_variables[ess]] for t in range(T)]) - lambda_param * price_diff_penalty
    )

    prob = cp.Problem(objective, cons)
    try:
        prob.solve(
            solver=cp.MOSEK,
            mosek_params={
                "MSK_IPAR_NUM_THREADS": 2,
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
        # print("优化后的目标函数值（Objective）：", prob.value)
        schedules = {}
        soc_matrix = np.zeros((T, es_num))
        power_matrix = np.zeros((T, es_num))
        penalty_charge_matrix = np.full((T, es_num), np.nan)
        bid_discharge_matrix = np.full((T, es_num), np.nan)
        for idx, ess in enumerate(ess_params):
            schedules[ess] = pd.DataFrame({
                'Hour': range(T),
                'Charge': ess_variables[ess]['charge'].value,
                'Discharge': ess_variables[ess]['discharge'].value,
                'SOC': ess_variables[ess]['soc'].value
            })
            soc_matrix[:, idx] = ess_variables[ess]['soc'].value
            power_matrix[:, idx] = -(ess_variables[ess]['discharge'].value - ess_variables[ess]['charge'].value)
            for t in range(T):
                if ess_variables[ess]['charge'].value[t] > 1e-3:
                    penalty_charge_matrix[t, idx] = 1e3
                else:
                    penalty_charge_matrix[t, idx] = -1e10
                if ess_variables[ess]['discharge'].value[t] > 1e-3:
                    bid_discharge_matrix[t, idx] = -1e3
                else:
                    bid_discharge_matrix[t, idx] = 1e10

        # 返回字典
        result = {
            'schedules': schedules,
            'soc_matrix': soc_matrix,
            'power_matrix': power_matrix,
            'penalty_charge_matrix': penalty_charge_matrix,
            'bid_discharge_matrix': bid_discharge_matrix
        }

        # 获取当前文件夹路径
        output_dir = os.path.join(os.path.dirname(__file__), 'results')
        os.makedirs(output_dir, exist_ok=True)

        # 保存文件
        output_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(__file__))[0]}_result_{sceneid}.xlsx")
        with pd.ExcelWriter(output_path) as writer:
            for ess_name, df in schedules.items():
                df.to_excel(writer, sheet_name=f"{ess_name}_schedule", index=False)
            pd.DataFrame(soc_matrix, columns=schedules.keys()).to_excel(writer, sheet_name="SOC_Matrix",
                                                                        index=False)
            pd.DataFrame(power_matrix, columns=schedules.keys()).to_excel(writer, sheet_name="Power_Matrix",
                                                                          index=False)
            pd.DataFrame(penalty_charge_matrix, columns=schedules.keys()).to_excel(writer, sheet_name="Charge_Bid",
                                                                                   index=False)
            pd.DataFrame(bid_discharge_matrix, columns=schedules.keys()).to_excel(writer,
                                                                                  sheet_name="Discharge_Bid",
                                                                                  index=False)
        print(f"已将储能优化运行结果保存到 '{os.path.splitext(os.path.basename(__file__))[0]}_result_{sceneid}.xlsx'")
        return result
    else:
        raise RuntimeError("优化失败，未找到可行解")
        return None

# 主程序
if __name__ == "__main__":
    from make_ieee30_uc_opf_es import ieee30_uc_opf_es_dict
    try:
        MAIN_CASE_ID = 3
        sceneid = MAIN_CASE_ID
        case_example = ieee30_uc_opf_es_dict(sceneid)

        # 提取相关参数
        T = case_example['T']

        TG_offer = case_example['TG_offer'].astype(float)
        TG_carbon = case_example['TG_carbon'].astype(float)
        TG_maxG = case_example['TG_maxG'].astype(float)
        TG_minG = case_example['TG_minG'].astype(float)
        TG_ramp = case_example['TG_ramp'].astype(float)
        T_on = case_example['T_on']
        T_off = case_example['T_off']
        RG_offer = case_example['RG_offer'].astype(float)
        RG_P = case_example['RG_P'].astype(float)
        RG_ramp = case_example['RG_ramp'].astype(float)
        RG_cap = case_example['RG_cap'].astype(float)
        D_num = case_example['D_num']
        D_P = case_example['D_P'].astype(float)
        # 储能相关参数
        ES_num = case_example['ES_num']
        ES_ramp = case_example['ES_ramp'].astype(float)
        ES_P = case_example['ES_P'].astype(float)
        eff = case_example['eff'].astype(float)

        # 调用 PTDF 函数
        PTDF_result = PTDF(case_example)

        PTDF = PTDF_result['PTDF']
        branch_max = PTDF_result['branch_max']
        A_TG = PTDF_result['A_TG']
        A_RG = PTDF_result['A_RG']
        A_D = PTDF_result['A_D']
        A_ES = PTDF_result['A_ES']

        # 调用函数
        u = uc(sceneid, T, TG_offer, TG_maxG, TG_minG, TG_ramp, T_on, T_off, RG_offer, RG_P, RG_cap,
               RG_ramp, D_P, branch_max, PTDF, A_TG, A_RG, A_D)['u']

        LMP_matrix = run_opf_carbon(sceneid, T, u, TG_carbon, TG_offer, TG_maxG, TG_minG,
                                    RG_offer, RG_P, RG_cap, D_P, branch_max, PTDF, A_TG, A_RG, A_D, D_num)['LMP']

        prices = (LMP_matrix @ A_ES).T  # 使用 A_ES 指定的节点索引，shape: (num_ess, T)
        print(prices)

        result = optimize_ess_schedule(T, prices, sceneid, ES_num, ES_ramp, ES_P, eff)

        if result:
            print("已成功获取并返回储能优化结果")
            schedules = result['schedules']
            penalty_charge_matrix = result['penalty_charge_matrix']
            bid_discharge_matrix = result['bid_discharge_matrix']
            soc_matrix = result['soc_matrix']
            power_matrix = result['power_matrix']

            # 打印输出结果
            print("ESS1 运行曲线：")
            print(schedules['ESS1'])
            print("ESS2 运行曲线：")
            print(schedules['ESS2'])
            print("储能电量矩阵（SOC）:")
            print(pd.DataFrame(soc_matrix, columns=schedules.keys()))
            print("储能功率矩阵（充电 - 放电）:")
            print(pd.DataFrame(power_matrix, columns=schedules.keys()))
            print("储能充电未消纳惩罚系数矩阵:")
            print(pd.DataFrame(penalty_charge_matrix, columns=schedules.keys()))
            print("储能放电报价矩阵:")
            print(pd.DataFrame(bid_discharge_matrix, columns=schedules.keys()))

            # np.save("penalty_charge_matrix.npy", penalty_charge_matrix)
            # np.save("bid_discharge_matrix.npy", bid_discharge_matrix)
            # print("已保存储能报价矩阵至 'penalty_charge_matrix.npy' 和 'bid_discharge_matrix.npy'")


    except Exception as e:
        print(f"运行出错：{str(e)}")
