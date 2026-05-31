import os
import sys
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir)

import pickle

import numpy as np
import pandas as pd


def result_workbook_name(T):
    if int(T) == 24:
        return "kernelshap_ieee14_price_taking_base_24h.xlsx"
    if int(T) == 168:
        return "kernelshap_ieee30_manuscript_168h.xlsx"
    return f"kernelshap_main_{int(T)}h.xlsx"


def write_excel(case_id, T):
    """
    将每个时段的 SHAP 和 total_time 数据写入 Excel 子表，添加时间戳 t
    :param case_id: internal case identifier used to locate intermediate .npy files
    :param T: 时间步数
    :param output_dir: 存储 .npy 文件的目录
    """
    output_dir = os.path.join(base_dir, 'kernel_data_RG')

    # 初始化数据存储列表
    shap_data_list = []
    shap_origin_data_list = []
    total_time_data_list = []
    shap_all_data_sum = None  # 用于存储 SHAP_all 的累加数据
    total_time_all = 0  # 用于存储总时间的累加值

    # 遍历所有时段 t
    for t in range(T):
        # 从 .npy 文件中读取数据
        shap_t = np.load(os.path.join(output_dir, f'shap_{case_id}_{t}.npy'))
        shap_origin_t = np.load(os.path.join(output_dir, f'shap_origin_{case_id}_{t}.npy'))
        shap_all_t = np.load(os.path.join(output_dir, f'shap_all_{case_id}_{t}.npy'))
        total_time_t = np.round(np.load(os.path.join(output_dir, f'total_time_{case_id}_{t}.npy')), 2)

        # 累加 SHAP_all 数据
        if shap_all_data_sum is None:
            shap_all_data_sum = shap_all_t.copy()
        else:
            shap_all_data_sum += shap_all_t

        # 累加 TotalTime_all 数据
        total_time_all += total_time_t

        # 将当前时段的数据添加到列表中
        shap_data_list.append([t] + shap_t.tolist())  # 将 t 和 shap_t 合并成一个列表
        shap_origin_data_list.append([t] + shap_origin_t.tolist())
        total_time_data_list.append([t] + [total_time_t])

    # 创建 DataFrame 存储数据
    columns_shap_t = ["t"] + [f"agent_{i}" for i in range(shap_t.shape[0])]
    df_shap = pd.DataFrame(shap_data_list, columns=columns_shap_t)

    columns_shap_t_origin = ["t"] + [f"agent_{i}" for i in range(shap_origin_t.shape[0])]
    df_shap_origin = pd.DataFrame(shap_origin_data_list, columns=columns_shap_t_origin)

    df_total_time = pd.DataFrame(total_time_data_list, columns=["t", "TotalTime_t"])

    columns_shap_all = [f"agent_{i}" for i in range(shap_all_t.shape[1])]
    df_shap_all = pd.DataFrame(shap_all_data_sum, columns=columns_shap_all)

    df_total_time_all = pd.DataFrame([total_time_all], columns=["TotalTime_all"])

    results_dir = os.path.join(base_dir, 'kernel_SHAP_results')
    os.makedirs(results_dir, exist_ok=True)

    # 输出到 Excel 文件
    result_file = os.path.join(results_dir, result_workbook_name(T))
    with pd.ExcelWriter(result_file) as writer:
        df_shap.to_excel(writer, sheet_name="SHAP_t", index=False)
        df_shap_origin.to_excel(writer, sheet_name="SHAP_t_origin", index=False)
        df_total_time.to_excel(writer, sheet_name="TotalTime_t", index=False)
        df_shap_all.to_excel(writer, sheet_name="SHAP_all", index=False)
        df_total_time_all.to_excel(writer, sheet_name="TotalTime_all", index=False)

if __name__ == "__main__":
    MAIN_CASE_ID = 3
    pkl_file_path = os.path.join(base_dir, 'data', f'case_example_dict_{MAIN_CASE_ID}.pkl')
    with open(pkl_file_path, 'rb') as f:
        case_example = pickle.load(f)
    T = int(case_example['T'])  # 获取时间步数 T
    write_excel(MAIN_CASE_ID, T)
    print(f"=== KernelSHAP workbook generated: {result_workbook_name(T)} ===")

    print("=== 所有 kernel_SHAP 结果文件已生成 ===")
