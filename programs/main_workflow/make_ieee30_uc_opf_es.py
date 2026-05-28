import os
import sys
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir)
repo_dir = os.path.abspath(os.path.join(base_dir, "..", ".."))
profile_dir = os.path.join(repo_dir, "data", "input_profiles")

import random

import numpy as np
import pandas as pd

def ieee30_uc_opf_es_dict(sceneid):
    # 时间粒度参数
    day = 7
    granu = 24
    T = granu * day

    # 机组&负荷参数
    # G = 335 - 381.7   RG / G = 20.9% - 43.7%  D / G = 56%
    TG_num = 4
    RG_num = 2
    D_num = 20
    bus_num = 30
    branch_num = 41
    TG_bl = [1, 2, 22, 27]
    TG_offer = [400, 400, 450, 850]
    TG_carbon = [1.044, 1.044, 1.044, 0.44]
    TG_maxG = [80, 80, 50, 55] # 265 coal-coal-coal-gas
    TG_minG = [28, 28, 18, 14] # coal-35% gas-25%
    TG_ramp = [48, 48, 30, 330] # coal-60%(1%/min) gas-600%(10%/min)
    T_on = [4, 4, 2, 1]
    T_off = [6, 6, 4, 1]
    RG_bl = [23, 13]
    RG_offer = [0, 0]
    RG_P = [30, 40]
    RG_ramp = [30, 40]
    D_bl = [2, 3, 4, 7, 8, 10, 12, 14, 15, 16, 17, 18, 19, 20, 21, 23, 24, 26, 29, 30]
    D_P_base = [21.7, 2.4, 7.6, 22.8, 30.0, 5.8, 11.2, 6.2, 8.2, 3.5, 9.0, 3.2, 9.5, 2.2, 17.5, 3.2, 8.7, 3.5, 2.4, 10.6];  # 基础负荷需求=189.2
    branch = np.array([
        [1,    2,    0.02,  0.06,  0.03,  130, 130, 130,  0,  0,  1,  -360, 360],
        [1,    3,    0.05,  0.19,  0.02,  130, 130, 130,  0,  0,  1,  -360, 360],
        [2,    4,    0.06,  0.17,  0.02,  65,  65,  65,   0,  0,  1,  -360, 360],
        [3,    4,    0.01,  0.04,  0,     130, 130, 130,  0,  0,  1,  -360, 360],
        [2,    5,    0.05,  0.20,  0.02,  130, 130, 130,  0,  0,  1,  -360, 360],
        [2,    6,    0.06,  0.18,  0.02,  65,  65,  65,   0,  0,  1,  -360, 360],
        [4,    6,    0.01,  0.04,  0,     90,  90,  90,   0,  0,  1,  -360, 360],
        [5,    7,    0.05,  0.12,  0.01,  70,  70,  70,   0,  0,  1,  -360, 360],
        [6,    7,    0.03,  0.08,  0.01,  130, 130, 130,  0,  0,  1,  -360, 360],
        [6,    8,    0.01,  0.04,  0,     32,  32,  32,   0,  0,  1,  -360, 360],
        [6,    9,    0,     0.21,  0,     65,  65,  65,   0,  0,  1,  -360, 360],
        [6,    10,   0,     0.56,  0,     32,  32,  32,   0,  0,  1,  -360, 360],
        [9,    11,   0,     0.21,  0,     65,  65,  65,   0,  0,  1,  -360, 360],
        [9,    10,   0,     0.11,  0,     65,  65,  65,   0,  0,  1,  -360, 360],
        [4,    12,   0,     0.26,  0,     65,  65,  65,   0,  0,  1,  -360, 360],
        [12,   13,   0,     0.14,  0,     65,  65,  65,   0,  0,  1,  -360, 360],
        [12,   14,   0.12,  0.26,  0,     32,  32,  32,   0,  0,  1,  -360, 360],
        [12,   15,   0.07,  0.13,  0,     32,  32,  32,   0,  0,  1,  -360, 360],
        [12,   16,   0.09,  0.20,  0,     32,  32,  32,   0,  0,  1,  -360, 360],
        [14,   15,   0.22,  0.20,  0,     16,  16,  16,   0,  0,  1,  -360, 360],
        [16,   17,   0.08,  0.19,  0,     16,  16,  16,   0,  0,  1,  -360, 360],
        [15,   18,   0.11,  0.22,  0,     16,  16,  16,   0,  0,  1,  -360, 360],
        [18,   19,   0.06,  0.13,  0,     16,  16,  16,   0,  0,  1,  -360, 360],
        [19,   20,   0.03,  0.07,  0,     32,  32,  32,   0,  0,  1,  -360, 360],
        [10,   20,   0.09,  0.21,  0,     32,  32,  32,   0,  0,  1,  -360, 360],
        [10,   17,   0.03,  0.08,  0,     32,  32,  32,   0,  0,  1,  -360, 360],
        [10,   21,   0.03,  0.07,  0,     32,  32,  32,   0,  0,  1,  -360, 360],
        [10,   22,   0.07,  0.15,  0,     32,  32,  32,   0,  0,  1,  -360, 360],
        [21,   22,   0.01,  0.02,  0,     32,  32,  32,   0,  0,  1,  -360, 360],
        [15,   23,   0.10,  0.20,  0,     16,  16,  16,   0,  0,  1,  -360, 360],
        [22,   24,   0.12,  0.18,  0,     16,  16,  16,   0,  0,  1,  -360, 360],
        [23,   24,   0.13,  0.27,  0,     16,  16,  16,   0,  0,  1,  -360, 360],
        [24,   25,   0.19,  0.33,  0,     16,  16,  16,   0,  0,  1,  -360, 360],
        [25,   26,   0.25,  0.38,  0,     16,  16,  16,   0,  0,  1,  -360, 360],
        [25,   27,   0.11,  0.21,  0,     16,  16,  16,   0,  0,  1,  -360, 360],
        [28,   27,   0,     0.40,  0,     65,  65,  65,   0,  0,  1,  -360, 360],
        [27,   29,   0.22,  0.42,  0,     16,  16,  16,   0,  0,  1,  -360, 360],
        [27,   30,   0.32,  0.60,  0,     16,  16,  16,   0,  0,  1,  -360, 360],
        [29,   30,   0.24,  0.45,  0,     16,  16,  16,   0,  0,  1,  -360, 360],
        [8,    28,   0.06,  0.20,  0.02,  32,  32,  32,   0,  0,  1,  -360, 360],
        [6,    28,   0.02,  0.06,  0.01,  32,  32,  32,   0,  0,  1,  -360, 360]
    ])[:, [0, 1, 3, 5]]  # 只保留部分列

    # 储能节点参数
    ES_num = 2
    ES_bl = [13, 23]  # 储能节点
    ES_ramp = [20, 30]  # 最大充放电功率=35  # ES / 1.8D = 14.7%
    # ES_ramp = [10, 15]  # 最大充放电功率=35  # ES / 1.8D = 7.34%
    ES_P = [40, 60]  # 储能容量
    # ES_P = [20, 30]  # 储能容量
    ES_offer = [0, 0]  # 储能供电价格
    eff = [0.9, 0.9]  # 储能充/放电效率

    # 读取 Excel 文件
    file_path = os.path.join(profile_dir, 'ieee30_profile_data.xlsx')
    df = pd.read_excel(file_path)

    # 提取某天的数据
    day_of_interest = 300
    start_row = (day_of_interest - 1) * granu
    end_row = start_row + T
    data_of_day = df.iloc[start_row:end_row, 0:8]  #负荷
    RG_cap = np.array(df.iloc[start_row:end_row, -2:])  # 新能源出力上限

    # 随机为每个负荷分配列并计算实际负荷需求
    random.seed(1126)
    random_cols = [random.randint(0, 7) for _ in range(D_num)]  # 生成D_num个随机列索引(0-7)

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
    class ieee30_uc_opf_es:
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
            self.D_P = np.array(D_P) * 1.8
            self.branch = np.array(branch)

            self.ES_bl = np.array(ES_bl).astype(int)
            # self.ES_ramp = np.array(ES_ramp) * sceneid
            # self.ES_P = np.array(ES_P) * sceneid
            self.ES_ramp = np.array(ES_ramp)
            self.ES_P = np.array(ES_P)
            self.ES_offer = np.array(ES_offer)
            self.eff = np.array(eff)

    case_save = ieee30_uc_opf_es()
    ieee30_uc_opf_es_dict = case_save.__dict__

    return ieee30_uc_opf_es_dict
