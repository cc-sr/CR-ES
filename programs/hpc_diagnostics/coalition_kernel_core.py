import os
import pickle
import sys
import time

import cvxpy as cp
import numpy as np

_WORKER_CONTEXT = None


def patch_numpy_pickle_compatibility():
    try:
        import numpy.core as numpy_core
        import numpy.core._multiarray_umath as numpy_core_multiarray_umath
        import numpy.core.multiarray as numpy_core_multiarray
        import numpy.core.numeric as numpy_core_numeric
        import numpy.core.umath as numpy_core_umath
    except Exception:
        return
    sys.modules.setdefault("numpy._core", numpy_core)
    sys.modules.setdefault("numpy._core._multiarray_umath", numpy_core_multiarray_umath)
    sys.modules.setdefault("numpy._core.multiarray", numpy_core_multiarray)
    sys.modules.setdefault("numpy._core.numeric", numpy_core_numeric)
    sys.modules.setdefault("numpy._core.umath", numpy_core_umath)


def load_case(case_path):
    patch_numpy_pickle_compatibility()
    with open(case_path, "rb") as f:
        return pickle.load(f)


def make_ptdf(case):
    a_tg = np.zeros((case["bus_num"], case["TG_num"]))
    for idx, bus in enumerate(case["TG_bl"].astype(int)):
        a_tg[bus - 1, idx] = 1

    a_rg = np.zeros((case["bus_num"], case["RG_num"]))
    for idx, bus in enumerate(case["RG_bl"].astype(int)):
        a_rg[bus - 1, idx] = 1

    a_d = np.zeros((case["bus_num"], case["D_num"]))
    for idx, bus in enumerate(case["D_bl"].astype(int)):
        a_d[bus - 1, idx] = 1

    b_line = np.zeros((case["bus_num"], case["bus_num"]))
    b_line_inv = np.zeros((case["bus_num"], case["bus_num"]))
    x_line = np.zeros((case["branch_num"], case["bus_num"]))
    for idx in range(case["branch_num"]):
        f_bus = int(case["branch"][idx, 0] - 1)
        t_bus = int(case["branch"][idx, 1] - 1)
        x = case["branch"][idx, 2]
        b_line[f_bus, t_bus] -= 1 / x
        b_line[t_bus, f_bus] -= 1 / x
        b_line[f_bus, f_bus] += 1 / x
        b_line[t_bus, t_bus] += 1 / x
        x_line[idx, f_bus] = 1 / x
        x_line[idx, t_bus] = -1 / x

    b_line_inv[:-1, :-1] = np.linalg.inv(b_line[:-1, :-1])
    ptdf = x_line @ b_line_inv
    active = np.nonzero(case["branch"][:, 3])[0]
    return {
        "PTDF": ptdf[active, :],
        "branch_max": case["branch"][active, 3].astype(float),
        "A_TG": a_tg,
        "A_RG": a_rg,
        "A_D": a_d,
    }


def solve_problem(problem):
    threads = int(os.getenv("MOSEK_NUM_THREADS", "1"))
    problem.solve(
        solver=cp.MOSEK,
        mosek_params={
            "MSK_IPAR_NUM_THREADS": threads,
            "MSK_DPAR_INTPNT_TOL_REL_GAP": 1e-4,
            "MSK_DPAR_INTPNT_TOL_PFEAS": 1e-4,
            "MSK_DPAR_INTPNT_TOL_DFEAS": 1e-4,
        },
        verbose=False,
    )
    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        raise RuntimeError(f"Coalition OPF failed with status {problem.status}")


def coalition_carbon_value(case, ptdf_data, t, coalition):
    tg_num = int(case["TG_num"])
    rg_num = int(case["RG_num"])
    d_num = int(case["D_num"])

    coalition = np.asarray(coalition, dtype=float)
    u_t = case["u_TG"][t, :].astype(float)
    tg_mask = coalition[:tg_num]
    rg_mask = coalition[tg_num : tg_num + rg_num]
    d_mask = coalition[tg_num + rg_num :]

    tg_offer = case["TG_offer"].astype(float)
    tg_carbon = case["TG_carbon"].astype(float)
    tg_max = case["TG_maxG"].astype(float) * tg_mask
    tg_min = case["TG_minG"].astype(float) * tg_mask
    rg_offer = case["RG_offer"].astype(float)
    rg_p = case["RG_P"].astype(float) * rg_mask
    rg_cap_t = case["RG_cap"][t, :].astype(float)
    d_p_t = case["D_P"][t, :].astype(float) * d_mask

    load_shed_penalty = float(case.get("load_shed_penalty", 5000.0))
    thermal_curtailment_penalty = float(case.get("thermal_curtailment_penalty", 200.0))
    renewable_curtailment_penalty = float(case.get("renewable_curtailment_penalty", 100.0))

    pg = cp.Variable(tg_num)
    apg = cp.Variable(tg_num)
    rg = cp.Variable(rg_num)
    ls = cp.Variable(d_num)
    pd = d_p_t - ls

    renewable_available = rg_cap_t * rg_p
    objective = (
        cp.sum(cp.multiply(tg_offer, pg - apg))
        + thermal_curtailment_penalty * cp.sum(apg)
        + cp.sum(cp.multiply(rg_offer, rg))
        + renewable_curtailment_penalty * cp.sum(renewable_available - rg)
        + load_shed_penalty * cp.sum(ls)
    )

    net_injection = (
        ptdf_data["A_TG"] @ (pg - apg)
        + ptdf_data["A_RG"] @ rg
        - ptdf_data["A_D"] @ pd
    )
    flow = ptdf_data["PTDF"] @ net_injection

    constraints = [
        cp.sum(pg - apg) + cp.sum(rg) == cp.sum(pd),
        flow <= ptdf_data["branch_max"],
        flow >= -ptdf_data["branch_max"],
        tg_min * u_t <= pg,
        pg <= tg_max * u_t,
        0 <= rg,
        rg <= renewable_available,
        0 <= ls,
        ls <= d_p_t,
        0 <= apg,
        apg <= pg,
        apg <= case["TG_minG"].astype(float),
    ]

    problem = cp.Problem(cp.Minimize(objective), constraints)
    solve_problem(problem)
    return float(tg_carbon @ (pg.value - apg.value))


def shapley_kernel_sample_size_probabilities(n_agents):
    p = np.zeros(n_agents + 1, dtype=float)
    for k in range(1, n_agents):
        p[k] = (n_agents - 1) / (k * (n_agents - k))
    return p / np.sum(p)


def write_random_samples(output_dir, n_agents, kernel_num, samples_per_kernel, seed):
    os.makedirs(output_dir, exist_ok=True)
    for name in os.listdir(output_dir):
        if name.startswith("randomS_") and name.endswith(".npy"):
            os.remove(os.path.join(output_dir, name))
    rng = np.random.default_rng(seed)
    p_size = shapley_kernel_sample_size_probabilities(n_agents)
    for kernel_id in range(kernel_num):
        sizes = rng.choice(np.arange(n_agents + 1), samples_per_kernel, p=p_size)
        samples = np.zeros((samples_per_kernel, n_agents), dtype=np.int8)
        for sid, size in enumerate(sizes):
            samples[sid, rng.choice(n_agents, int(size), replace=False)] = 1
        np.save(os.path.join(output_dir, f"randomS_{kernel_id}.npy"), samples)


def load_random_sample(random_dir, kernel_id, sid):
    return np.load(os.path.join(random_dir, f"randomS_{kernel_id}.npy"))[sid].astype(float)


def solve_constrained_kernel_regression(a_sum, b_sum, sample_count, full_value):
    a_mean = a_sum / sample_count
    b_mean = (b_sum / sample_count).reshape((-1, 1))
    a_inv = np.linalg.pinv(a_mean)
    ones = np.ones((a_mean.shape[0], 1))
    correction = (ones.T @ a_inv @ b_mean - full_value) / (ones.T @ a_inv @ ones)
    phi = a_inv @ (b_mean - ones * correction)
    return phi.reshape(-1)


def participant_labels(case):
    tg_labels = [f"TG{i + 1}" for i in range(case["TG_num"])]
    real_rg_num = int(case["real_RG_num"])
    es_num = int(case["ES_num"])
    real_d_num = int(case["real_D_num"])
    rg_labels = [f"RG{i + 1}" for i in range(real_rg_num)]
    es_dis_labels = [f"ES{i + 1}_dis" for i in range(es_num)]
    d_labels = [f"D{i + 1}" for i in range(real_d_num)]
    es_ch_labels = [f"ES{i + 1}_ch" for i in range(es_num)]
    return tg_labels + rg_labels + es_dis_labels + d_labels + es_ch_labels


def merged_labels(case):
    tg_labels = [f"TG{i + 1}" for i in range(case["TG_num"])]
    rg_labels = [f"RG{i + 1}" for i in range(case["real_RG_num"])]
    d_labels = [f"D{i + 1}" for i in range(case["real_D_num"])]
    es_labels = [f"ES{i + 1}" for i in range(case["ES_num"])]
    return tg_labels + rg_labels + d_labels + es_labels


def merge_ess_roles(case, phi_origin):
    tg_num = int(case["TG_num"])
    rg_num = int(case["RG_num"])
    real_rg_num = int(case["real_RG_num"])
    d_num = int(case["D_num"])
    real_d_num = int(case["real_D_num"])
    es_num = int(case["ES_num"])

    tg_part = phi_origin[:tg_num]
    real_rg_part = phi_origin[tg_num : tg_num + real_rg_num]
    es_dis_part = phi_origin[tg_num + real_rg_num : tg_num + rg_num]
    d_start = tg_num + rg_num
    real_d_part = phi_origin[d_start : d_start + real_d_num]
    es_ch_part = phi_origin[d_start + real_d_num : d_start + d_num]
    return np.concatenate([tg_part, real_rg_part, real_d_part, es_dis_part + es_ch_part])


def compute_period_kernel(
    case_path,
    case_tag,
    period,
    kernel_num,
    samples_per_kernel,
    checkpoint_every,
    workers,
):
    from concurrent.futures import ProcessPoolExecutor, as_completed

    base_dir = os.path.abspath(os.path.dirname(__file__))
    output_dir = os.path.join(base_dir, "kernel_data", case_tag)
    os.makedirs(output_dir, exist_ok=True)

    case = load_case(case_path)
    ptdf_data = make_ptdf(case)
    n_agents = int(case["TG_num"] + case["RG_num"] + case["D_num"])
    full_value = coalition_carbon_value(case, ptdf_data, period, np.ones(n_agents))

    start = time.time()
    tasks = [(kid, sid) for kid in range(kernel_num) for sid in range(samples_per_kernel)]
    a_by_kernel = np.zeros((kernel_num, n_agents, n_agents), dtype=float)
    b_by_kernel = np.zeros((kernel_num, n_agents), dtype=float)

    if workers <= 1:
        _init_period_worker(case_path, case_tag, period)
        for task in tasks:
            kernel_id, a_update, b_update = _run_sample_worker(task)
            a_by_kernel[kernel_id] += a_update
            b_by_kernel[kernel_id] += b_update
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_period_worker,
            initargs=(case_path, case_tag, period),
        ) as executor:
            futures = {executor.submit(_run_sample_worker, task): task for task in tasks}
            for future in as_completed(futures):
                kernel_id, a_update, b_update = future.result()
                a_by_kernel[kernel_id] += a_update
                b_by_kernel[kernel_id] += b_update

    total_time = time.time() - start
    checkpoints = sorted(
        set([0] + [k for k in range(checkpoint_every - 1, kernel_num, checkpoint_every)] + [kernel_num - 1])
    )
    origin_path = []
    merged_path = []
    sample_counts = []
    a_sum = np.zeros((n_agents, n_agents), dtype=float)
    b_sum = np.zeros(n_agents, dtype=float)
    checkpoint_set = set(checkpoints)
    for kernel_id in range(kernel_num):
        a_sum += a_by_kernel[kernel_id]
        b_sum += b_by_kernel[kernel_id]
        if kernel_id in checkpoint_set:
            count = (kernel_id + 1) * samples_per_kernel
            phi = solve_constrained_kernel_regression(a_sum, b_sum, count, full_value)
            origin_path.append(phi)
            merged_path.append(merge_ess_roles(case, phi))
            sample_counts.append(count)
    origin_final = np.asarray(origin_path)[-1]
    merged_final = np.asarray(merged_path)[-1]
    np.save(os.path.join(output_dir, f"shap_origin_{period}.npy"), origin_final)
    np.save(os.path.join(output_dir, f"shap_merged_{period}.npy"), merged_final)
    np.save(os.path.join(output_dir, f"shap_all_{period}.npy"), np.asarray(merged_path))
    np.save(os.path.join(output_dir, f"sample_counts_{period}.npy"), np.asarray(sample_counts))
    np.save(os.path.join(output_dir, f"fai_all_{period}.npy"), np.asarray(full_value))
    np.save(os.path.join(output_dir, f"total_time_{period}.npy"), np.asarray(total_time))
    return origin_final, merged_final, full_value, total_time


def _init_period_worker(case_path, case_tag, period):
    global _WORKER_CONTEXT
    base_dir = os.path.abspath(os.path.dirname(__file__))
    case = load_case(case_path)
    _WORKER_CONTEXT = {
        "case": case,
        "ptdf_data": make_ptdf(case),
        "period": int(period),
        "random_dir": os.path.join(base_dir, "random_S_set", case_tag),
    }


def _run_sample_worker(task):
    kernel_id, sid = task
    case = _WORKER_CONTEXT["case"]
    ptdf_data = _WORKER_CONTEXT["ptdf_data"]
    period = _WORKER_CONTEXT["period"]
    random_dir = _WORKER_CONTEXT["random_dir"]
    x = load_random_sample(random_dir, kernel_id, sid)
    value = coalition_carbon_value(case, ptdf_data, period, x)
    return kernel_id, np.outer(x, x), x * value
