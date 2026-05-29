import os
import sys
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir)
repo_dir = os.path.abspath(os.path.join(base_dir, "..", ".."))
profile_dir = os.path.join(repo_dir, "data", "input_profiles")

import random

import numpy as np
import pandas as pd

def ieee14_uc_opf_es_dict(sceneid):
    # 时间粒度参数
    day = 1
    granu = 24
    T = granu * day

    # 机组&负荷参数
    # G = 855    RG / G = 33%   D / G = 30%
    TG_num = 3
    RG_num = 2
    D_num = 11
    bus_num = 14
    branch_num = 20
    TG_bl = [1, 2, 3]
    TG_offer = [350, 400, 800]
    TG_carbon = [1.044, 1.044, 0.44]
    TG_maxG = [332, 140, 100] # 572 coal-coal-gas
    TG_minG = [120, 50, 25] # coal-35% gas-25%
    TG_ramp = [200, 84, 600] # coal-60% gas-600%
    TG_start_cost = [265600, 112000, 15000]
    TG_stop_cost = [53120, 22400, 3000]
    T_on = [6, 4, 1]
    T_off = [8, 6, 1]
    RG_bl = [6, 8]
    RG_offer = [0, 0]
    RG_P = [100, 100]
    RG_ramp = [100, 100]
    D_bl = [2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14]
    D_P_base = [21.7, 94.2, 47.8, 7.6, 11.2, 29.5, 9, 3.5, 6.1, 13.5, 14.9]  # 基础负荷需求=259
    branch = np.array([
        [1, 2,   0.01938, 0.05917, 0.0528, 80, 0, 0, 0,     0, 1, -360, 360],
        [1, 5,   0.05403, 0.22304, 0.0492, 80, 0, 0, 0,     0, 1, -360, 360],
        [2, 3,   0.04699, 0.19797, 0.0438, 80, 0, 0, 0,     0, 1, -360, 360],
        [2, 4,   0.05811, 0.17632, 0.034,  80, 0, 0, 0,     0, 1, -360, 360],
        [2, 5,   0.05695, 0.17388, 0.0346, 80, 0, 0, 0,     0, 1, -360, 360],
        [3, 4,   0.06701, 0.17103, 0.0128, 80, 0, 0, 0,     0, 1, -360, 360],
        [4, 5,   0.01335, 0.04211, 0,      80, 0, 0, 0,     0, 1, -360, 360],
        [4, 7,   0,       0.20912, 0,      80, 0, 0, 0.978, 0, 1, -360, 360],
        [4, 9,   0,       0.55618, 0,      80, 0, 0, 0.969, 0, 1, -360, 360],
        [5, 6,   0,       0.25202, 0,      80, 0, 0, 0.932, 0, 1, -360, 360],
        [6, 11,  0.09498, 0.1989,  0,      80, 0, 0, 0,     0, 1, -360, 360],
        [6, 12,  0.12291, 0.25581, 0,      80, 0, 0, 0,     0, 1, -360, 360],
        [6, 13,  0.06615, 0.13027, 0,      80, 0, 0, 0,     0, 1, -360, 360],
        [7, 8,   0,       0.17615, 0,      80, 0, 0, 0,     0, 1, -360, 360],
        [7, 9,   0,       0.11001, 0,      80, 0, 0, 0,     0, 1, -360, 360],
        [9, 10,  0.03181, 0.0845,  0,      80, 0, 0, 0,     0, 1, -360, 360],
        [9, 14,  0.12711, 0.27038, 0,      80, 0, 0, 0,     0, 1, -360, 360],
        [10, 11, 0.08205, 0.19207, 0,      80, 0, 0, 0,     0, 1, -360, 360],
        [12, 13, 0.22092, 0.19988, 0,      80, 0, 0, 0,     0, 1, -360, 360],
        [13, 14, 0.17093, 0.34802, 0,      80, 0, 0, 0,     0, 1, -360, 360]
    ])[:, [0, 1, 3, 5]]  # 只保留部分列

    # 储能节点参数
    ES_num = 2
    ES_bl = [4, 5]  # 储能节点
    ES_ramp = [20, 15]  # 最大充放电功率
    ES_P = [40, 30]  # 储能容量=70  # ES / 1.9D = 14.68%
    ES_offer = [0, 0]  # 储能供电价格
    eff = [0.9, 0.95]  # 储能充/放电效率

    # 读取 Excel 文件
    file_path = os.path.join(profile_dir, 'ieee14_profile_data.xlsx')
    df = pd.read_excel(file_path)

    # 提取某天的数据
    day_of_interest = 150
    start_row = (day_of_interest - 1) * granu
    end_row = start_row + T
    data_of_day = df.iloc[start_row:end_row, 0:8]  #负荷
    RG_cap = np.array(df.iloc[start_row:end_row, -2:])  # 新能源出力上限

    # 随机为每个负荷分配列并计算实际负荷需求
    random.seed(1126)
    random_cols = [random.randint(0, 7) for _ in range(D_num)]  # 生成11个随机列索引(0-7)

    loads = {}
    for i in range(D_num):
        load_num = i + 1
        col = random_cols[i]
        normalized_data = data_of_day.iloc[:, col].values
        base_load = D_P_base[i]
        load_profile = normalized_data * base_load
        loads[f"Load {load_num}"] = load_profile

    D_P = np.array([loads[f"Load {i}"] for i in range(1, D_num+1)]).T

    # 定义数据结构类
    class ieee14_uc_opf_es:
        def __init__(self):
            self.sceneid = sceneid

            self.T = T
            self.TG_num = TG_num
            self.RG_num = RG_num
            self.D_num = D_num
            self.ES_num = ES_num
            self.bus_num = bus_num
            self.branch_num = branch_num

            self.TG_bl = np.array(TG_bl).astype(int)
            self.TG_offer = np.array(TG_offer)
            self.TG_carbon = np.array(TG_carbon)
            self.TG_maxG = np.array(TG_maxG)
            self.TG_minG = np.array(TG_minG)
            self.TG_ramp = np.array(TG_ramp)
            self.TG_start_cost = np.array(TG_start_cost)
            self.TG_stop_cost = np.array(TG_stop_cost)
            self.T_on = np.array(T_on)
            self.T_off = np.array(T_off)
            self.RG_bl = np.array(RG_bl).astype(int)
            self.RG_offer = np.array(RG_offer)
            self.RG_P = np.array(RG_P) * sceneid * 0.2/0.6  # 170/0.6=283
            self.RG_ramp = np.array(RG_ramp) /0.6
            # self.RG_P = np.array(RG_P)  # 170
            # self.RG_ramp = np.array(RG_ramp)
            self.RG_cap = np.array(RG_cap)
            self.D_bl = np.array(D_bl).astype(int)
            self.D_P = np.array(D_P)
            self.branch = np.array(branch)

            self.ES_bl = np.array(ES_bl).astype(int)
            # self.ES_ramp = np.array(ES_ramp) * sceneid
            # self.ES_P = np.array(ES_P) * sceneid
            self.ES_ramp = np.array(ES_ramp)
            self.ES_P = np.array(ES_P)
            self.ES_offer = np.array(ES_offer)
            self.eff = np.array(eff)

    case_save = ieee14_uc_opf_es()
    ieee14_uc_opf_es_dict = case_save.__dict__

    return ieee14_uc_opf_es_dict
