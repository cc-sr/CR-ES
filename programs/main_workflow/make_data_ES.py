import warnings
warnings.filterwarnings("ignore")

import os
import sys
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir)

import numpy as np

from make_ieee30_uc_opf_es import ieee30_uc_opf_es_dict

import make_case_example_no_storage
import make_case_example

import make_PTDF
import make_PTDF_es

from run_uc import uc
from run_uc_es import uc_es
from run_es_legacy import optimize_ess_schedule

import opf_lmp_carbon

from make_randomS import randomS

base_dir = os.path.abspath(os.path.dirname(__file__))

def data(sceneid):
    case_example_es = ieee30_uc_opf_es_dict(sceneid)

    # 提取相关参数
    T = case_example_es['T']

    TG_offer = case_example_es['TG_offer'].astype(float)
    TG_carbon = case_example_es['TG_carbon'].astype(float)
    TG_maxG = case_example_es['TG_maxG'].astype(float)
    TG_minG = case_example_es['TG_minG'].astype(float)
    TG_ramp = case_example_es['TG_ramp'].astype(float)
    T_on = case_example_es['T_on']
    T_off = case_example_es['T_off']
    RG_offer = case_example_es['RG_offer'].astype(float)
    RG_P = case_example_es['RG_P'].astype(float)
    RG_ramp = case_example_es['RG_ramp'].astype(float)
    RG_cap = case_example_es['RG_cap'].astype(float)
    D_P = case_example_es['D_P'].astype(float)
    D_num = int(case_example_es['D_num'])
    # 储能相关参数
    ES_num = int(case_example_es['ES_num'])
    ES_ramp = case_example_es['ES_ramp'].astype(float)
    ES_P = case_example_es['ES_P'].astype(float)
    eff = case_example_es['eff'].astype(float)

    # 调用 PTDF 函数
    PTDF_result = make_PTDF_es.PTDF(case_example_es)

    PTDF = PTDF_result['PTDF']
    branch_max = PTDF_result['branch_max']
    A_TG = PTDF_result['A_TG']
    A_RG = PTDF_result['A_RG']
    A_D = PTDF_result['A_D']
    A_ES = PTDF_result['A_ES']

    # 调用uc_es函数
    u = uc(sceneid, T, TG_offer, TG_maxG, TG_minG, TG_ramp, T_on, T_off, RG_offer, RG_P, RG_cap,
           RG_ramp, D_P, branch_max, PTDF, A_TG, A_RG, A_D)['u']

    if sceneid == 0:
        case_example = make_case_example_no_storage.case_example_dict(sceneid, case_example_es, u)

    else:
        LMP_matrix = opf_lmp_carbon.run_opf_carbon(sceneid, T, u, TG_carbon, TG_offer, TG_maxG, TG_minG,
                                                   RG_offer, RG_P, RG_cap, D_P, branch_max, PTDF, A_TG, A_RG, A_D, D_num)['LMP']

        prices = (LMP_matrix @ A_ES).T
        ess_result = optimize_ess_schedule(T, prices, sceneid, ES_num, ES_ramp, ES_P, eff)

        # 储能报价矩阵
        penalty_charge_matrix = ess_result['penalty_charge_matrix']
        bid_discharge_matrix = ess_result['bid_discharge_matrix']

        uc_es_result = uc_es(sceneid, T, TG_offer, TG_maxG, TG_minG, TG_ramp, T_on, T_off, RG_offer, RG_P, RG_cap,
                             RG_ramp, D_P, branch_max, PTDF, A_TG, A_RG, A_D, A_ES, ES_ramp, ES_P, eff,
                             penalty_charge_matrix, bid_discharge_matrix)

        u_TG_matrix = uc_es_result["u"]

        p_charge_matrix = np.maximum(0, uc_es_result["s"])
        p_discharge_matrix = -np.minimum(0, uc_es_result["s"])
        p_discharge_matrix[p_discharge_matrix == -0.0] = 0.0
        p_discharge_matrix = p_discharge_matrix / ES_ramp

        case_example = make_case_example.case_example_dict(sceneid, case_example_es, u_TG_matrix, p_charge_matrix, p_discharge_matrix)

    TG_num = case_example['TG_num']
    RG_num = case_example['RG_num']
    D_num = case_example['D_num']

    # 计算每个博弈者的Shapley值
    agents_num = TG_num + RG_num + D_num

    randomS(agents_num)

    pkl_file_path = os.path.join(base_dir, 'data', f'case_example_dict_{sceneid}.pkl')

    PTDF_result = make_PTDF.PTDF(pkl_file_path)

    PTDF = PTDF_result['PTDF']
    branch_max = PTDF_result['branch_max']
    A_TG = PTDF_result['A_TG']
    A_RG = PTDF_result['A_RG']
    A_D = PTDF_result['A_D']
    case_example = PTDF_result['case_example']

    u = case_example['u_TG'].astype(int)
    TG_carbon = case_example['TG_carbon'].astype(float)
    TG_offer = case_example['TG_offer'].astype(float)
    TG_maxG = case_example['TG_maxG'].astype(float)
    TG_minG = case_example['TG_minG'].astype(float)
    RG_offer = case_example['RG_offer'].astype(float)
    RG_P = case_example['RG_P'].astype(float)
    RG_cap = case_example['RG_cap'].astype(float)
    D_P = case_example['D_P'].astype(float)

    opf_lmp_carbon.run_opf_carbon(sceneid, T, u, TG_carbon, TG_offer, TG_maxG, TG_minG,
                   RG_offer, RG_P, RG_cap, D_P, branch_max, PTDF, A_TG, A_RG, A_D, D_num)

    print("=== 所有数据预处理完成 ===")
    return case_example
