import warnings
warnings.filterwarnings("ignore")

import os
import sys
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir)

import pickle

import make_data

def write_t_script(sceneid, t, case_label="main"):
    script_path = os.path.join(base_dir, 'make_kernel_RG', f'kernel_data_{case_label}_t_{t}.py')
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    with open(script_path, 'w') as f:
        f.write(f"""import warnings
warnings.filterwarnings("ignore")

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

import time
import traceback
import numpy as np

from make_PTDF import PTDF
import opf_es_carbon
# from kernel_SHAP_RG_IEEE14 import kernel_SHAP
from kernel_SHAP_RG_IEEE30 import kernel_SHAP

from multiprocessing import cpu_count
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError

def load_random_sample(file_dir, file_id, sid, kernel_id, samples_num):
    file_path = os.path.join(file_dir, f'randomS_{{file_id}}.npy')
    random_sample = np.load(file_path)[(sid + kernel_id * samples_num) % 100]
    return random_sample

def compute_output(u_t, TG_num, RG_num, TG_carbon, TG_offer, TG_maxG, TG_minG, RG_offer, RG_P, RG_cap_t, D_P_t,
                   x_input, branch_max, PTDF, A_TG, A_RG, A_D):
    output = opf_es_carbon.opf_carbon(
        u_t, TG_carbon, TG_offer,
        TG_maxG * x_input[: TG_num],
        TG_minG * x_input[: TG_num],
        RG_offer, RG_P * x_input[TG_num: TG_num + RG_num],
        RG_cap_t, D_P_t * x_input[TG_num + RG_num:],
        branch_max, PTDF, A_TG, A_RG, A_D
    )['carbon_t']
    An_update = x_input.reshape(-1, 1) @ x_input.reshape(1, -1)
    bn_update = x_input * output
    return An_update, bn_update

def flattened_process_sample(args):
    (kernel_id, sid, random_sample_dir, samples_num,
     t, u_t, TG_num, RG_num, TG_carbon, TG_offer, TG_maxG, TG_minG,
     RG_offer, RG_P, RG_cap_t, D_P_t, branch_max, PTDF, A_TG, A_RG, A_D) = args

    try:
        start_time = time.time()
        file_id = (sid + kernel_id * samples_num) // 100
        x_input = load_random_sample(random_sample_dir, file_id, sid, kernel_id, samples_num)
        # print(x_input, flush=True)
        An_update, bn_update = compute_output(
            u_t, TG_num, RG_num, TG_carbon, TG_offer, TG_maxG, TG_minG,
            RG_offer, RG_P, RG_cap_t, D_P_t, x_input, branch_max, PTDF, A_TG, A_RG, A_D
        )
        elapsed_time = time.time() - start_time
        return kernel_id, sid, An_update, bn_update, elapsed_time
    except Exception as error:
        print(f"Error processing Kernel ID {{kernel_id}} Sample ID {{sid}}: {{error}}", flush=True)
        traceback.print_exc()
        return kernel_id, sid, None, None, None


if __name__ == "__main__":
    MAIN_CASE_ID = {sceneid}
    random_sample_dir = os.path.join(base_dir, 'random_S_set')

    pkl_file_path = os.path.join(base_dir, 'data', f'case_example_dict_{{MAIN_CASE_ID}}.pkl')

    PTDF_result = PTDF(pkl_file_path)

    PTDF = PTDF_result['PTDF']
    branch_max = PTDF_result['branch_max']
    A_TG = PTDF_result['A_TG']
    A_RG = PTDF_result['A_RG']
    A_D = PTDF_result['A_D']
    case_example = PTDF_result['case_example']

    TG_num = int(case_example['TG_num'])
    RG_num = int(case_example['RG_num'])
    D_num = int(case_example['D_num'])
    ES_num = int(case_example['ES_num'])

    u = case_example['u_TG'].astype(int)
    TG_carbon = case_example['TG_carbon'].astype(float)
    TG_offer = case_example['TG_offer'].astype(float)
    TG_maxG = case_example['TG_maxG'].astype(float)
    TG_minG = case_example['TG_minG'].astype(float)
    RG_offer = case_example['RG_offer'].astype(float)
    RG_P = case_example['RG_P'].astype(float)
    RG_cap = case_example['RG_cap'].astype(float)
    D_P = case_example['D_P'].astype(float)

    agents_num = TG_num + RG_num + D_num

    kernel_num = 3000
    start_kernel = 0
    samples_num = 100
    rand_num = 1

    sceneid = MAIN_CASE_ID
    t = {t}
    u_t = u [t, :]
    D_P_t = D_P[t, :]
    RG_cap_t = RG_cap[t, :]

    # Initialize accumulators for each kernel_id and rand_num
    all_An = [[None for _ in range(kernel_num)] for _ in range(rand_num)]
    all_bn = [[None for _ in range(kernel_num)] for _ in range(rand_num)]
    all_time = [[0.0 for _ in range(kernel_num)] for _ in range(rand_num)]

    # Prepare all tasks for all kernel_id and sample_id combinations
    tasks = []
    for kernel_id in range(start_kernel, kernel_num):
        for sid in range(samples_num):
            task_args = (
                kernel_id, sid, random_sample_dir, samples_num,
                t, u_t, TG_num, RG_num, TG_carbon, TG_offer, TG_maxG, TG_minG,
                RG_offer, RG_P, RG_cap_t, D_P_t, branch_max, PTDF, A_TG, A_RG, A_D
            )
            tasks.append(task_args)

    TIMEOUT = 60
    with ProcessPoolExecutor(max_workers=cpu_count()) as executor:
    # with ProcessPoolExecutor(max_workers=int(os.getenv('SLURM_CPUS_PER_TASK'))) as executor:
        future_to_task = {{executor.submit(flattened_process_sample, task): task for task in tasks}}
        for future in as_completed(future_to_task):
            try:
                kernel_id, sid, An_update, bn_update, elapsed_time = future.result()
                if An_update is not None and bn_update is not None:
                    for randid in range(rand_num):
                        if all_An[randid][kernel_id] is None:
                            all_An[randid][kernel_id] = An_update
                            all_bn[randid][kernel_id] = bn_update
                        else:
                            all_An[randid][kernel_id] += An_update
                            all_bn[randid][kernel_id] += bn_update
                        all_time[randid][kernel_id] += elapsed_time
                else:
                    print(f"Task Failed: Kernel ID {{kernel_id}}, Sample ID {{sid}}", flush=True)
            except TimeoutError:
                print(f"Timeout: Kernel ID {{kernel_id}}, Sample ID {{sid}}")
            except Exception as e:
                print(f"Error: Kernel ID {{kernel_id}}, Sample ID {{sid}}, {{e}}", flush=True)

    fai_all = opf_es_carbon.opf_carbon(u_t, TG_carbon, TG_offer, TG_maxG, TG_minG, RG_offer, RG_P, RG_cap_t,
               D_P_t, branch_max, PTDF, A_TG, A_RG, A_D)['carbon_t']
    
    # SHAP
    kernel_SHAP(t, sceneid, fai_all, agents_num, ES_num, kernel_num, rand_num, all_An, all_bn, all_time)

    print(f"=== kernel_data_{case_label}_t_{{t}} 处理完成 ===")
""")

def main():
    MAIN_CASE_ID = 3
    make_data.data(MAIN_CASE_ID)

    pkl_file_path = os.path.join(base_dir, 'data', f'case_example_dict_{MAIN_CASE_ID}.pkl')
    with open(pkl_file_path, 'rb') as f:
        case_example = pickle.load(f)
    T = int(case_example['T'])

    for t in range(T):
        write_t_script(MAIN_CASE_ID, t, case_label="main")
    print("=== 所有 kernel_data_main_t 脚本已生成 ===")

if __name__ == "__main__":
    main()
