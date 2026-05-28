import numpy as np

def PTDF(case_example):
    """
    计算 PTDF 矩阵和相关信息。
    :param file_path: str, 包含电网数据的 pickle 文件路径
    :return: dict, 包括 PTDF 矩阵
    """

    # 节点-火电矩阵
    A_TG = np.zeros((case_example['bus_num'], case_example['TG_num']))
    for i_TG in range(case_example['TG_num']):
        A_TG[case_example['TG_bl'][i_TG] - 1, i_TG] = 1

    # 节点-新能源矩阵
    A_RG = np.zeros((case_example['bus_num'], case_example['RG_num']))
    for i_RG in range(case_example['RG_num']):
        A_RG[case_example['RG_bl'][i_RG] - 1, i_RG] = 1

    # 节点-负荷矩阵
    A_D = np.zeros((case_example['bus_num'], case_example['D_num']))
    for i_D in range(case_example['D_num']):
        A_D[case_example['D_bl'][i_D] - 1, i_D] = 1

    # 节点-储能矩阵
    A_ES = np.zeros((case_example['bus_num'], case_example['ES_num']))
    for i_ES in range(case_example['ES_num']):
        A_ES[case_example['ES_bl'][i_ES] - 1, i_ES] = 1

    # 计算 PTDF
    B_line = np.zeros((case_example['bus_num'], case_example['bus_num']))
    B_line_inv = np.zeros((case_example['bus_num'], case_example['bus_num']))
    X_line = np.zeros((case_example['branch_num'], case_example['bus_num']))
    for i_branch in range(case_example['branch_num']):
        f_bus = int(case_example['branch'][i_branch, 0] - 1)
        t_bus = int(case_example['branch'][i_branch, 1] - 1)
        x = case_example['branch'][i_branch, 2]
        B_line[f_bus, t_bus] -= 1 / x
        B_line[t_bus, f_bus] -= 1 / x
        B_line[f_bus, f_bus] += 1 / x
        B_line[t_bus, t_bus] += 1 / x
        X_line[i_branch, f_bus] = 1 / x
        X_line[i_branch, t_bus] = -1 / x

    B_line_inv[:-1, :-1] = np.linalg.inv(B_line[:-1, :-1])
    PTDF = np.matmul(X_line, B_line_inv)

    # 剔除 PTDF 中所有值接近 0 的行
    for row_index in range(PTDF.shape[0]):
        if np.all(np.abs(PTDF[row_index, :]) < 0.0001):
            case_example['branch'][row_index, 3] = 0

    # 找出需要进行潮流约束的 branch
    branch_check_id = np.nonzero(case_example['branch'][:, 3])[0]
    PTDF = PTDF[branch_check_id, :]
    branch_max = 1.0 * case_example['branch'][branch_check_id, 3]

    return {
        'PTDF': PTDF,
        'branch_max': branch_max,
        'A_TG': A_TG,
        'A_RG': A_RG,
        'A_D': A_D,
        'A_ES': A_ES,
        # 'case_example': case_example
    }

