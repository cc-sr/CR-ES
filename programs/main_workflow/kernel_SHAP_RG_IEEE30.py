import warnings
warnings.filterwarnings("ignore")

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__)))

import time
import numpy as np

# 设置项目根目录
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir)

def kernel_SHAP(t, sceneid, fai_all, agents_num, ES_num, kernel_num, rand_num, all_An, all_bn, all_time):
    para_num = kernel_num
    SHAP_t = np.zeros((para_num // 5 + 1, agents_num - ES_num))
    SHAP_all = np.zeros((para_num // 5 + 1, agents_num - ES_num))
    total_time_all = 0

    SHAP_origin = np.zeros((rand_num, para_num // 5 + 1, agents_num))
    total_time_t = np.zeros((rand_num, para_num // 5 + 1))

    for randid in range(rand_num):
        total_time = 0
        An = 0
        bn = 0
        for kernel_id in range(para_num):
            An_id = all_An[randid][kernel_id]
            bn_id = all_bn[randid][kernel_id]
            total_time_id = all_time[randid][kernel_id]

            An += An_id
            bn += bn_id
            total_time += total_time_id

            if kernel_id == 0:
                start_time = time.time()
                numsample = (kernel_id + 1) * 100
                this_An_ = np.linalg.inv(An / numsample)
                this_bn = (bn / numsample).reshape((-1, 1))
                SHAP = this_An_ @ (this_bn - np.ones((agents_num, 1)) * (
                        np.ones((1, agents_num)) @ this_An_ @ this_bn - fai_all) /
                                   (np.ones((1, agents_num)) @ this_An_ @ np.ones((agents_num, 1))))
                end_time = time.time()
                SHAP_origin[randid, 0] = SHAP.reshape(-1) * 1.0
                # SHAP_t[sceneid, randid, 0] = SHAP.reshape(-1) * 1.0
                total_time_t[randid, 0] = total_time + end_time - start_time

            if kernel_id % 5 == 4:
                start_time = time.time()
                numsample = (kernel_id + 1) * 100
                this_An_ = np.linalg.inv(An / numsample)
                this_bn = (bn / numsample).reshape((-1, 1))
                SHAP = this_An_ @ (this_bn - np.ones((agents_num, 1)) * (
                        np.ones((1, agents_num)) @ this_An_ @ this_bn - fai_all) /
                                   (np.ones((1, agents_num)) @ this_An_ @ np.ones((agents_num, 1))))
                end_time = time.time()
                SHAP_origin[randid, kernel_id // 5 + 1] = SHAP.reshape(-1).astype(float)
                # SHAP_t[sceneid, randid, kernel_id // 5 + 1] = SHAP.reshape(-1).astype(float)
                total_time_t[randid, kernel_id // 5 + 1] = total_time + end_time - start_time

            # 合并 SHAP_origin的 agent5+agent18, agent6+agent19
            SHAP_origin_reshape = SHAP_origin.reshape(-1, SHAP_origin.shape[-1])

            # 合并列
            SHAP_t = np.hstack((
                SHAP_origin_reshape[:, 0:6],
                SHAP_origin_reshape[:, 8:28],
                (SHAP_origin_reshape[:, 6] + SHAP_origin_reshape[:, 28]).reshape(-1, 1),  # 第5列 + 第18列
                (SHAP_origin_reshape[:, 7] + SHAP_origin_reshape[:, 29]).reshape(-1, 1)   # 第6列 + 第19列
            ))

    SHAP_all += SHAP_t
    total_time_all += total_time_t[-1, -1]

    # 打印最后一组 SHAP_t 和 total_time_t 的值
    print(f"SHAP_{t}:")
    print(SHAP_t[-1, :])  # 获取 SHAP_t 的最后一组值
    print(f"SHAP_{t}_origin:")
    print(SHAP_origin[-1, -1])  # 获取 SHAP_t 的最后一组值
    print("SHAP:")
    print(SHAP_all[-1,:])  # 获取 SHAP_all 的最后一组值
    print("Total carbon emission:")
    print(np.sum(SHAP_all[-1,:]))
    print(f"total_time_{t}:")
    print(total_time_t[-1, -1])  # 获取 total_time_t 的最后一组值
    print("total_time:")
    print(f'{total_time_all:.2f}')  # 获取 total_time_all

    output_dir = os.path.join(base_dir, 'kernel_data_RG')
    os.makedirs(output_dir, exist_ok=True)

    # 保存为 .npy 文件
    np.save(os.path.join(output_dir, f'shap_{sceneid}_{t}.npy'), SHAP_t[-1, :])
    np.save(os.path.join(output_dir, f'shap_origin_{sceneid}_{t}.npy'), SHAP_origin[-1, -1])
    np.save(os.path.join(output_dir, f'total_time_{sceneid}_{t}.npy'), total_time_t[-1, -1])
    np.save(os.path.join(output_dir, f'shap_all_{sceneid}_{t}.npy'), SHAP_all)
    # np.save(os.path.join(output_dir, f'total_time_all_{sceneid}_{t}.npy'), total_time_all)

    return