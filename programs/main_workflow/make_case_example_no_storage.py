import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__)))

import numpy as np
import pickle

def case_example_dict(sceneid, case_example_es, u):
    # 提取相关参数
    T = case_example_es['T']

    TG_num = case_example_es['TG_num']
    RG_num = case_example_es['RG_num']
    D_num = case_example_es['D_num']
    ES_num = case_example_es['ES_num']
    bus_num = case_example_es['bus_num']
    branch_num = case_example_es['branch_num']

    TG_bl = case_example_es['TG_bl']
    TG_offer = case_example_es['TG_offer'].astype(float)
    TG_carbon = case_example_es['TG_carbon'].astype(float)
    TG_maxG = case_example_es['TG_maxG'].astype(float)
    TG_minG = case_example_es['TG_minG'].astype(float)
    TG_ramp = case_example_es['TG_ramp'].astype(float)
    T_on = case_example_es['T_on']
    T_off = case_example_es['T_off']
    RG_bl = case_example_es['RG_bl']
    RG_offer = case_example_es['RG_offer'].astype(float)
    RG_P = case_example_es['RG_P'].astype(float)
    RG_ramp = case_example_es['RG_ramp'].astype(float)
    RG_cap = case_example_es['RG_cap'].astype(float)
    D_bl = case_example_es['D_bl']
    D_P_base = case_example_es['D_P'].astype(float)
    branch = case_example_es['branch'].astype(float)

    # 定义数据结构类
    class case_example:
        def __init__(self):
            self.sceneid = int(sceneid)

            self.T = int(T)
            self.TG_num = int(TG_num)
            self.RG_num = int(RG_num)
            self.D_num = int(D_num)
            self.ES_num = int(ES_num)
            self.bus_num = int(bus_num)
            self.branch_num = int(branch_num)

            self.u = u
            self.TG_bl = np.array(TG_bl).astype(int)
            self.TG_offer = np.array(TG_offer)
            self.TG_carbon = np.array(TG_carbon)
            self.TG_maxG = np.array(TG_maxG)
            self.TG_minG = np.array(TG_minG)
            self.TG_ramp = np.array(TG_ramp)
            self.u_TG = np.array(u)
            self.T_on = np.array(T_on)
            self.T_off = np.array(T_off)

            self.RG_bl = np.array(RG_bl).astype(int)
            self.RG_offer = np.array(RG_offer)
            self.RG_P = np.array(RG_P)
            self.RG_ramp = np.array(RG_ramp)
            self.RG_cap = np.array(RG_cap)

            self.D_bl = np.array(D_bl).astype(int)
            self.D_P = np.array(D_P_base)

            self.branch = np.array(branch)

    # 保存
    case_save = case_example()
    case_example_dict = case_save.__dict__
    output_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, f'case_example_dict_{sceneid}.pkl'), 'wb') as cc:
        pickle.dump(case_example_dict, cc)

    print(f"已将无储能预处理数据保存到 case_example_dict_{sceneid}.pkl")
    return case_example_dict
