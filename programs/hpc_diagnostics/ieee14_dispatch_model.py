import os
import sys
import warnings

warnings.filterwarnings("ignore")

import cvxpy as cp
import numpy as np
import pandas as pd

HPC_DIAGNOSTICS_DIR = os.path.abspath(os.path.dirname(__file__))
MAIN_WORKFLOW_DIR = os.path.abspath(os.path.join(HPC_DIAGNOSTICS_DIR, "..", "main_workflow"))
REPO_DIR = os.path.abspath(os.path.join(HPC_DIAGNOSTICS_DIR, "..", ".."))
PROFILE_DIR = os.path.join(REPO_DIR, "data", "input_profiles")
sys.path.append(MAIN_WORKFLOW_DIR)

from make_ieee14_uc_opf_es import ieee14_uc_opf_es_dict  # noqa: E402
from make_PTDF_es import PTDF  # noqa: E402

COAL_CAPACITY_MW = 300.0


def thermal_commit_costs(tg_max, tg_carbon):
    per_mw = np.where(np.asarray(tg_carbon, dtype=float) < 0.7, 150.0, 800.0)
    start_cost = per_mw * np.asarray(tg_max, dtype=float)
    return start_cost, 0.2 * start_cost


def solve_problem(problem):
    gurobi_options = {
        "Threads": int(os.getenv("GUROBI_THREADS", "2")),
        "MIPGap": float(os.getenv("GUROBI_MIP_GAP", "1e-6")),
    }
    time_limit = os.getenv("GUROBI_TIME_LIMIT")
    if time_limit:
        gurobi_options["TimeLimit"] = float(time_limit)

    try:
        problem.solve(solver=cp.GUROBI, verbose=False, **gurobi_options)
    except cp.error.SolverError:
        problem.solve(
            solver=cp.MOSEK,
            mosek_params={
                "MSK_IPAR_NUM_THREADS": 2,
                "MSK_DPAR_INTPNT_TOL_REL_GAP": 1e-4,
                "MSK_DPAR_INTPNT_TOL_PFEAS": 1e-4,
                "MSK_DPAR_INTPNT_TOL_DFEAS": 1e-4,
            },
            verbose=False,
        )

    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        raise RuntimeError(f"Optimization failed with status: {problem.status}")


def retype_ieee14_case(case, bus2_profile="wind", bus3_profile="solar"):
    case = dict(case)

    original_rg_cap = case["RG_cap"].astype(float)
    solar_profile = original_rg_cap[:, 0]
    wind_profile = original_rg_cap[:, 1]
    rg2_profile = solar_profile if bus2_profile == "solar" else wind_profile
    rg3_profile = wind_profile if bus3_profile == "wind" else solar_profile

    case["TG_num"] = 2
    case["RG_num"] = 3

    case["TG_bl"] = np.array([6, 8]).astype(int)
    case["TG_offer"] = np.array([800, 350], dtype=float)
    case["TG_carbon"] = np.array([0.44, 1.044], dtype=float)
    case["TG_maxG"] = np.array([100, 100], dtype=float)
    case["TG_minG"] = np.array([25, 35], dtype=float)
    case["TG_ramp"] = np.array([600, 60], dtype=float)
    case["T_on"] = np.array([1, 6]).astype(int)
    case["T_off"] = np.array([1, 8]).astype(int)

    case["RG_bl"] = np.array([1, 2, 3]).astype(int)
    case["RG_offer"] = np.array([0, 0, 0], dtype=float)
    case["RG_P"] = np.array([332, 140, 100], dtype=float)
    case["RG_ramp"] = np.array([332, 140, 100], dtype=float)
    case["RG_cap"] = np.column_stack([wind_profile, rg2_profile, rg3_profile])

    return case


def load_case_with_data_file(data_file, resource_layout="original", ess_layout="original"):
    data_path = os.path.join(PROFILE_DIR, data_file)
    original_read_excel = pd.read_excel

    def read_excel_override(path, *args, **kwargs):
        if isinstance(path, str) and os.path.basename(path) == "ieee14_profile_data.xlsx":
            path = data_path
        return original_read_excel(path, *args, **kwargs)

    pd.read_excel = read_excel_override
    try:
        case = ieee14_uc_opf_es_dict(3)
    finally:
        pd.read_excel = original_read_excel

    if resource_layout == "retyped_123_renewable_68_thermal":
        case = retype_ieee14_case(case)
    elif resource_layout == "retyped_1wind_23solar_68_thermal":
        case = retype_ieee14_case(case, bus2_profile="solar")
    elif resource_layout == "retyped_13wind_2solar_68_thermal":
        case = retype_ieee14_case(case, bus2_profile="solar", bus3_profile="wind")
    elif resource_layout != "original":
        raise ValueError(f"Unsupported resource_layout: {resource_layout}")

    if ess_layout == "all_bus5":
        case["ES_bl"] = np.array([5, 5]).astype(int)
    elif ess_layout != "original":
        raise ValueError(f"Unsupported ess_layout: {ess_layout}")

    return case


def branch_key(f_bus, t_bus):
    return tuple(sorted((int(f_bus), int(t_bus))))


def apply_current_high_renewable_branch_limits(params, case):
    limits = []
    for f_bus, t_bus in case["branch"][:, :2].astype(int):
        key = branch_key(f_bus, t_bus)
        if key == (1, 2):
            limits.append(190.0)
        elif key == (1, 5):
            limits.append(240.0)
        elif key in {(2, 3), (2, 4), (2, 5), (3, 4), (4, 5)}:
            limits.append(100.0)
        elif key in {(7, 8), (7, 9)}:
            limits.append(200.0)
        else:
            limits.append(80.0)
    params["branch_max"] = np.array(limits, dtype=float)


def build_params(
    case,
    duration_h,
    load_scale=1.0,
    coal_capacity_mw=COAL_CAPACITY_MW,
    load_shed_penalty=5000.0,
    renewable_curtailment_penalty=100.0,
    thermal_curtailment_penalty=200.0,
    renewable_capacity_mw=None,
):
    case = dict(case)
    d_p = case["D_P"].astype(float) * float(load_scale)
    rg_p_base = case["RG_P"].astype(float)

    if coal_capacity_mw is not None:
        case["TG_maxG"] = case["TG_maxG"].astype(float)
        case["TG_ramp"] = case["TG_ramp"].astype(float)
        case["TG_maxG"][1] = float(coal_capacity_mw)
        case["TG_ramp"][1] = 0.6 * float(coal_capacity_mw)

    if renewable_capacity_mw is not None:
        renewable_capacity_mw = np.asarray(renewable_capacity_mw, dtype=float)
        if renewable_capacity_mw.shape != rg_p_base.shape:
            raise ValueError("renewable_capacity_mw must match the renewable generator count.")
        case["RG_P"] = renewable_capacity_mw
        case["RG_ramp"] = renewable_capacity_mw.copy()
    tg_start_cost, tg_stop_cost = thermal_commit_costs(case["TG_maxG"], case["TG_carbon"])

    ptdf_data = PTDF(case)
    return {
        "T": int(case["T"]),
        "TG_offer": case["TG_offer"].astype(float),
        "TG_carbon": case["TG_carbon"].astype(float),
        "TG_maxG": case["TG_maxG"].astype(float),
        "TG_minG": case["TG_minG"].astype(float),
        "TG_ramp": case["TG_ramp"].astype(float),
        "TG_start_cost": tg_start_cost,
        "TG_stop_cost": tg_stop_cost,
        "T_on": case["T_on"].astype(int),
        "T_off": case["T_off"].astype(int),
        "RG_offer": case["RG_offer"].astype(float),
        "RG_P": case["RG_P"].astype(float),
        "RG_cap": case["RG_cap"].astype(float),
        "RG_ramp": case["RG_ramp"].astype(float),
        "D_P": d_p,
        "ES_ramp": case["ES_ramp"].astype(float),
        "ES_P": case["ES_P"].astype(float),
        "eff": case["eff"].astype(float),
        "PTDF": ptdf_data["PTDF"],
        "branch_max": ptdf_data["branch_max"].astype(float),
        "A_TG": ptdf_data["A_TG"],
        "A_RG": ptdf_data["A_RG"],
        "A_D": ptdf_data["A_D"],
        "A_ES": ptdf_data["A_ES"],
        "load_energy": float(np.sum(d_p)),
        "load_peak": float(np.max(np.sum(d_p, axis=1))),
        "load_scale": float(load_scale),
        "coal_capacity_mw": np.nan if coal_capacity_mw is None else float(coal_capacity_mw),
        "load_shed_penalty": float(load_shed_penalty),
        "renewable_curtailment_penalty": float(renewable_curtailment_penalty),
        "thermal_curtailment_penalty": float(thermal_curtailment_penalty),
        "use_apg_slack": True,
        "renewable_available_energy": float(np.sum(case["RG_cap"] * case["RG_P"])),
    }


def extend_horizon(params, days):
    if days == 1:
        return
    params["T"] *= int(days)
    params["D_P"] = np.tile(params["D_P"], (int(days), 1))
    params["RG_cap"] = np.tile(params["RG_cap"], (int(days), 1))
    params["load_energy"] = float(np.sum(params["D_P"]))
    params["load_peak"] = float(np.max(np.sum(params["D_P"], axis=1)))
    params["renewable_available_energy"] = float(np.sum(params["RG_cap"] * params["RG_P"]))


def build_latest_params(es1_mw, es2_mw, duration_h=4.0, days=3):
    case = load_case_with_data_file(
        "ieee14_profile_data.xlsx",
        resource_layout="retyped_13wind_2solar_68_thermal",
        ess_layout="original",
    )
    params = build_params(
        case,
        duration_h=duration_h,
        coal_capacity_mw=COAL_CAPACITY_MW,
        renewable_capacity_mw=np.array([580.0, 260.0, 190.0]),
    )
    apply_current_high_renewable_branch_limits(params, case)
    extend_horizon(params, int(days))
    params["ES_ramp"] = np.array([float(es1_mw), float(es2_mw)])
    params["ES_P"] = float(duration_h) * params["ES_ramp"]
    params["initial_u"] = np.ones(len(params["TG_maxG"]))
    params["degradation_cost"] = 5.0
    params["dispatch_mode"] = "endogenous_storage_sensitivity"
    return params


def solve_uc_endogenous_storage(params, degradation_cost=5.0, cap_storage_discharge_by_load=False):
    t_count = params["T"]
    tg_offer = params["TG_offer"]
    tg_max = params["TG_maxG"]
    tg_min = params["TG_minG"]
    tg_ramp = params["TG_ramp"]
    tg_start_cost = params.get("TG_start_cost", np.zeros_like(tg_max)).astype(float)
    tg_stop_cost = params.get("TG_stop_cost", np.zeros_like(tg_max)).astype(float)
    t_on = params["T_on"]
    t_off = params["T_off"]
    rg_offer = params["RG_offer"]
    rg_p = params["RG_P"]
    rg_cap = params["RG_cap"]
    rg_ramp = params["RG_ramp"]
    d_p = params["D_P"]
    es_ramp = params["ES_ramp"]
    es_p = params["ES_P"]
    eff = params["eff"]
    branch_max = params["branch_max"]
    ptdf_m = params["PTDF"]
    a_tg = params["A_TG"]
    a_rg = params["A_RG"]
    a_d = params["A_D"]
    a_es = params["A_ES"]

    n_tg = len(tg_max)
    n_rg = len(rg_p)
    n_d = d_p.shape[1]
    n_es = len(es_ramp)
    renewable_available = rg_cap * rg_p.reshape(1, n_rg)

    ac = params.get("load_shed_penalty", 1e3)
    ag = params.get("thermal_curtailment_penalty", 1e2)
    rc = params.get("renewable_curtailment_penalty", 0.0)

    pg = cp.Variable((t_count, n_tg))
    apg = cp.Variable((t_count, n_tg))
    rg = cp.Variable((t_count, n_rg))
    ls = cp.Variable((t_count, n_d))
    p_charge = cp.Variable((t_count, n_es), nonneg=True)
    p_discharge = cp.Variable((t_count, n_es), nonneg=True)
    soc = cp.Variable((t_count + 1, n_es), nonneg=True)
    mode = cp.Variable((t_count, n_es), boolean=True)
    u = cp.Variable((t_count, n_tg), boolean=True)
    y = cp.Variable((t_count, n_tg), boolean=True)
    z = cp.Variable((t_count, n_tg), boolean=True)

    pd_served = d_p - ls
    obj = (
        cp.sum(cp.multiply(tg_offer.reshape(1, n_tg), pg - apg))
        + ag * cp.sum(apg)
        + cp.sum(cp.multiply(rg_offer.reshape(1, n_rg), rg))
        + rc * cp.sum(renewable_available - rg)
        + ac * cp.sum(ls)
        + degradation_cost * cp.sum(p_charge + p_discharge)
        + cp.sum(cp.multiply(tg_start_cost.reshape(1, n_tg), y))
        + cp.sum(cp.multiply(tg_stop_cost.reshape(1, n_tg), z))
    )

    cons = [soc[0, :] == 0.5 * es_p, soc[t_count, :] == 0.5 * es_p]
    initial_u = params.get("initial_u")
    if initial_u is not None:
        initial_u = np.asarray(initial_u, dtype=float)
        cons += [
            y[0, :] - z[0, :] == u[0, :] - initial_u,
            y[0, :] <= 1 - initial_u,
            z[0, :] <= initial_u,
        ]

    for t in range(t_count):
        cons += [0 <= pd_served[t, :], pd_served[t, :] <= d_p[t, :]]
        cons += [cp.multiply(u[t, :], tg_min) <= pg[t, :]]
        cons += [pg[t, :] <= cp.multiply(u[t, :], tg_max)]
        cons += [0 <= apg[t, :], apg[t, :] <= pg[t, :], apg[t, :] <= tg_min]

        for g in range(n_tg):
            t_on_g = int(t_on[g])
            t_off_g = int(t_off[g])
            if t + 1 >= t_on_g:
                cons += [cp.sum(y[t - t_on_g + 1 : t + 1, g]) <= u[t, g]]
            else:
                cons += [cp.sum(y[: t + 1, g]) <= u[t, g]]
            if t + 1 >= t_off_g:
                cons += [cp.sum(z[t - t_off_g + 1 : t + 1, g]) <= 1 - u[t, g]]
            else:
                cons += [cp.sum(z[: t + 1, g]) <= 1 - u[t, g]]

        if t > 0:
            cons += [y[t, :] - z[t, :] == u[t, :] - u[t - 1, :]]
            cons += [cp.abs(pg[t, :] - pg[t - 1, :]) <= tg_ramp]

        cons += [0 <= rg[t, :], rg[t, :] <= cp.multiply(rg_cap[t, :], rg_p)]
        if t > 0:
            cons += [cp.abs(rg[t, :] - rg[t - 1, :]) <= rg_ramp]

        cons += [p_charge[t, :] <= cp.multiply(es_ramp, 1 - mode[t, :])]
        cons += [p_discharge[t, :] <= cp.multiply(es_ramp, mode[t, :])]
        if cap_storage_discharge_by_load:
            cons += [cp.sum(p_discharge[t, :]) <= cp.sum(pd_served[t, :]) + cp.sum(p_charge[t, :])]
        cons += [
            soc[t + 1, :] == soc[t, :] + cp.multiply(eff, p_charge[t, :]) - cp.multiply(1 / eff, p_discharge[t, :]),
            soc[t + 1, :] <= es_p,
        ]

        cons += [
            cp.sum(pg[t, :] - apg[t, :]) + cp.sum(rg[t, :]) + cp.sum(p_discharge[t, :])
            == cp.sum(pd_served[t, :]) + cp.sum(p_charge[t, :])
        ]

        storage_injection = p_discharge[t, :] - p_charge[t, :]
        flow = (
            ptdf_m @ a_tg @ cp.reshape(pg[t, :] - apg[t, :], (-1, 1))
            + ptdf_m @ a_rg @ cp.reshape(rg[t, :], (-1, 1))
            - ptdf_m @ a_d @ cp.reshape(pd_served[t, :], (-1, 1))
            + ptdf_m @ a_es @ cp.reshape(storage_injection, (-1, 1))
        )
        cons += [flow <= branch_max.reshape((-1, 1)), flow >= -branch_max.reshape((-1, 1))]

    problem = cp.Problem(cp.Minimize(obj), cons)
    solve_problem(problem)

    return {
        "u": np.clip(np.round(u.value), 0, 1),
        "PG": pg.value,
        "APG": apg.value,
        "RG": rg.value,
        "PD": pd_served.value,
        "LS": ls.value,
        "p_charge": p_charge.value,
        "p_discharge": p_discharge.value,
        "soc": soc.value,
        "objective": problem.value,
    }


def solve_lmp_fixed_uc_storage(params, u_fixed, p_charge, p_discharge):
    t_count = params["T"]
    tg_offer = params["TG_offer"]
    tg_carbon = params["TG_carbon"]
    tg_max = params["TG_maxG"]
    tg_min = params["TG_minG"]
    rg_offer = params["RG_offer"]
    rg_p = params["RG_P"]
    rg_cap = params["RG_cap"]
    d_p = params["D_P"]
    branch_max = params["branch_max"]
    ptdf_m = params["PTDF"]
    a_tg = params["A_TG"]
    a_rg = params["A_RG"]
    a_d = params["A_D"]
    a_es = params["A_ES"]

    n_tg = len(tg_max)
    n_rg = len(rg_p)
    n_d = d_p.shape[1]
    n_bus = a_tg.shape[0]

    ac = params.get("load_shed_penalty", 1e3)
    ag = params.get("thermal_curtailment_penalty", 1e2)
    rc = params.get("renewable_curtailment_penalty", 0.0)
    lmp = np.zeros((t_count, n_bus))
    carbon = np.zeros(t_count)
    pg_out = np.zeros((t_count, n_tg))
    rg_out = np.zeros((t_count, n_rg))

    for t in range(t_count):
        pg = cp.Variable(n_tg)
        apg = cp.Variable(n_tg)
        rg = cp.Variable(n_rg)
        ls = cp.Variable(n_d)
        pd_served = d_p[t, :] - ls

        obj = (
            cp.sum(cp.multiply(tg_offer, pg - apg))
            + ag * cp.sum(apg)
            + cp.sum(cp.multiply(rg_offer, rg))
            + rc * cp.sum(cp.multiply(rg_cap[t, :], rg_p) - rg)
            + ac * cp.sum(ls)
        )

        fixed_storage_injection = p_discharge[t, :] - p_charge[t, :]
        balance = (
            cp.sum(pg - apg) + cp.sum(rg) + np.sum(p_discharge[t, :])
            == cp.sum(pd_served) + np.sum(p_charge[t, :])
        )
        flow = (
            ptdf_m @ a_tg @ cp.reshape(pg - apg, (-1, 1))
            + ptdf_m @ a_rg @ cp.reshape(rg, (-1, 1))
            - ptdf_m @ a_d @ cp.reshape(pd_served, (-1, 1))
            + ptdf_m @ a_es @ fixed_storage_injection.reshape((-1, 1))
        )
        flow_upper = flow <= branch_max.reshape((-1, 1))
        flow_lower = flow >= -branch_max.reshape((-1, 1))

        cons = [
            balance,
            flow_upper,
            flow_lower,
            tg_min * u_fixed[t, :] <= pg,
            pg <= tg_max * u_fixed[t, :],
            0 <= rg,
            rg <= rg_cap[t, :] * rg_p,
            0 <= ls,
            ls <= d_p[t, :],
            0 <= apg,
            apg <= pg,
            apg <= tg_min,
        ]

        problem = cp.Problem(cp.Minimize(obj), cons)
        solve_problem(problem)

        congestion = flow_upper.dual_value - flow_lower.dual_value
        lmp[t, :] = -balance.dual_value + ptdf_m.T @ congestion.reshape((-1,))
        carbon[t] = float(tg_carbon @ (pg.value - apg.value))
        pg_out[t, :] = pg.value - apg.value
        rg_out[t, :] = rg.value

    return {"LMP": lmp, "carbon": carbon, "PG": pg_out, "RG": rg_out}
