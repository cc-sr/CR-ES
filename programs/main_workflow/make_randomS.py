import os
import sys
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir)

import numpy as np

# def randomS(sceneid, agents_num):
def randomS(agents_num):
    np.random.seed(1126)
    p_list = np.zeros(agents_num + 1)
    for z_size in range(1, agents_num):
        p_list[z_size] = (agents_num - 1) / (z_size * (agents_num - z_size))
    # 归一化
    p_list = p_list / np.sum(p_list)
    for i in range(3000):
        # print(i, flush=True)
        # 生成整数,每一个服从p_list的分布
        randomS_one_num = np.random.choice(np.arange(agents_num + 1), 100, p=p_list)
        # 生成100*agents_num的01随机矩阵，每一个1的数量等于上面的整数
        randomS = np.zeros((100, agents_num))
        for j in range(100):
            randomS[j, np.random.choice(np.arange(agents_num), randomS_one_num[j], replace=False)] = 1

        output_dir = os.path.join(base_dir, 'random_S_set')  # 自动获取当前文件夹路径
        os.makedirs(output_dir, exist_ok=True)
        # np.save(os.path.join(output_dir, f'randomS_{sceneid}_' + str(i) + '.npy'), randomS)
        np.save(os.path.join(output_dir, f'randomS_' + str(i) + '.npy'), randomS)