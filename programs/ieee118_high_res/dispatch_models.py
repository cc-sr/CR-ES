import os
from pathlib import Path

import cvxpy as cp
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent


def solve_with_fallback(problem, mip=False, verbose=False):
    threads = int(os.getenv("SOLVER_THREADS", "2"))
    if mip:
        attempts = [
            (cp.GUROBI, {"Threads": threads, "MIPGap": float(os.getenv("GUROBI_MIPGAP", "1e-4"))}),
            (cp.MOSEK, {"mosek_params": {"MSK_IPAR_NUM_THREADS": threads}}),
        ]
    else:
        attempts = [
            (
                cp.MOSEK,
                {
                    "mosek_params": {
                        "MSK_IPAR_NUM_THREADS": threads,
                        "MSK_DPAR_INTPNT_TOL_REL_GAP": 1e-4,
                        "MSK_DPAR_INTPNT_TOL_PFEAS": 1e-4,
                        "MSK_DPAR_INTPNT_TOL_DFEAS": 1e-4,
                    }
                },
            ),
            (cp.GUROBI, {"Threads": threads}),
        ]

    last_error = None
    for solver, kwargs in attempts:
        try:
            problem.solve(solver=solver, verbose=verbose, **kwargs)
        except Exception as exc:
            last_error = exc
            continue
        if problem.status in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
            return solver
    raise RuntimeError(f"Optimization failed; status={problem.status}; last_error={last_error}")


def _commitment_constraints(cons, u, y, z, t, tg_count, t_on, t_off):
    for i in range(tg_count):
        on_len = int(t_on[i])
        off_len = int(t_off[i])
        if t + 1 >= on_len:
            cons += [cp.sum(y[t - on_len + 1 : t + 1, i]) <= u[t, i]]
        else:
            cons += [cp.sum(y[: t + 1, i]) <= u[t, i]]
        if t + 1 >= off_len:
            cons += [cp.sum(z[t - off_len + 1 : t + 1, i]) <= 1 - u[t, i]]
        else:
            cons += [cp.sum(z[: t + 1, i]) <= 1 - u[t, i]]


def solve_uc(
    case_tag,
    T,
    TG_offer,
    TG_maxG,
    TG_minG,
    TG_ramp,
    T_on,
    T_off,
    RG_offer,
    RG_P,
    RG_cap,
    RG_ramp,
    D_P,
    branch_max,
    PTDF,
    A_TG,
    A_RG,
    A_D,
    TG_start_cost,
    TG_stop_cost,
    initial_u=None,
    load_shed_penalty=5000.0,
    renewable_curtailment_penalty=100.0,
    thermal_curtailment_penalty=200.0,
):
    tg_count = len(TG_maxG)
    rg_count = len(RG_P)
    d_count = D_P.shape[1]

    PG = cp.Variable((T, tg_count))
    APG = cp.Variable((T, tg_count))
    RG = cp.Variable((T, rg_count))
    LS = cp.Variable((T, d_count))
    u = cp.Variable((T, tg_count), boolean=True)
    y = cp.Variable((T, tg_count), boolean=True)
    z = cp.Variable((T, tg_count), boolean=True)
    PD = D_P - LS

    renewable_available = RG_cap * RG_P.reshape(1, -1)
    obj = (
        cp.sum(cp.multiply(TG_offer.reshape(1, -1), PG - APG))
        + thermal_curtailment_penalty * cp.sum(APG)
        + cp.sum(cp.multiply(RG_offer.reshape(1, -1), RG))
        + renewable_curtailment_penalty * cp.sum(renewable_available - RG)
        + load_shed_penalty * cp.sum(LS)
    )
    if T > 1:
        obj += cp.sum(cp.multiply(TG_start_cost.reshape(1, -1), y[1:, :]))
        obj += cp.sum(cp.multiply(TG_stop_cost.reshape(1, -1), z[1:, :]))

    cons = []
    if initial_u is not None:
        initial_u = np.asarray(initial_u, dtype=float)
        cons += [
            y[0, :] - z[0, :] == u[0, :] - initial_u,
            y[0, :] <= 1 - initial_u,
            z[0, :] <= initial_u,
        ]

    for t in range(T):
        cons += [0 <= PD[t, :], PD[t, :] <= D_P[t, :]]
        cons += [
            cp.multiply(u[t, :], TG_minG) <= PG[t, :],
            PG[t, :] <= cp.multiply(u[t, :], TG_maxG),
            0 <= APG[t, :],
            APG[t, :] <= PG[t, :],
            APG[t, :] <= TG_minG,
            0 <= RG[t, :],
            RG[t, :] <= renewable_available[t, :],
        ]
        _commitment_constraints(cons, u, y, z, t, tg_count, T_on, T_off)

        if t > 0:
            cons += [y[t, :] - z[t, :] == u[t, :] - u[t - 1, :]]
            cons += [cp.abs(PG[t, :] - PG[t - 1, :]) <= TG_ramp]
            cons += [cp.abs(RG[t, :] - RG[t - 1, :]) <= RG_ramp]

        cons += [cp.sum(PG[t, :] - APG[t, :]) + cp.sum(RG[t, :]) == cp.sum(PD[t, :])]
        flow = PTDF @ (A_TG @ (PG[t, :] - APG[t, :]) + A_RG @ RG[t, :] - A_D @ PD[t, :])
        cons += [flow <= branch_max, flow >= -branch_max]

    problem = cp.Problem(cp.Minimize(obj), cons)
    solver = solve_with_fallback(problem, mip=True)
    result = {
        "PD": PD.value,
        "u": np.clip(np.round(u.value), 0, 1),
        "PG": PG.value,
        "LS": LS.value,
        "APG": APG.value,
        "RG": RG.value,
        "objective": float(problem.value),
        "solver": str(solver),
    }
    _write_dispatch_result(case_tag, "uc_no_es", result)
    return result


def solve_lmp_opf(
    case_tag,
    T,
    u,
    TG_carbon,
    TG_offer,
    TG_maxG,
    TG_minG,
    RG_offer,
    RG_P,
    RG_cap,
    D_P,
    branch_max,
    PTDF,
    A_TG,
    A_RG,
    A_D,
    load_shed_penalty=5000.0,
    renewable_curtailment_penalty=100.0,
    thermal_curtailment_penalty=200.0,
):
    carbon = 0.0
    carbon_list = []
    lmp = np.full((T, A_TG.shape[0]), np.nan)
    pg_rows = []
    apg_rows = []
    rg_rows = []

    for t in range(T):
        tg_count = len(TG_maxG)
        rg_count = len(RG_P)
        d_count = D_P.shape[1]
        pg = cp.Variable(tg_count)
        apg = cp.Variable(tg_count)
        rg = cp.Variable(rg_count)
        ls = cp.Variable(d_count)
        pd = D_P[t, :] - ls
        renewable_available = RG_cap[t, :] * RG_P

        obj = (
            cp.sum(cp.multiply(TG_offer, pg - apg))
            + thermal_curtailment_penalty * cp.sum(apg)
            + cp.sum(cp.multiply(RG_offer, rg))
            + renewable_curtailment_penalty * cp.sum(renewable_available - rg)
            + load_shed_penalty * cp.sum(ls)
        )
        flow = PTDF @ (A_TG @ (pg - apg) + A_RG @ rg - A_D @ pd)
        cons = [
            cp.sum(pg - apg) + cp.sum(rg) == cp.sum(pd),
            flow <= branch_max,
            flow >= -branch_max,
            TG_minG * u[t, :] <= pg,
            pg <= TG_maxG * u[t, :],
            0 <= rg,
            rg <= renewable_available,
            0 <= ls,
            ls <= D_P[t, :],
            0 <= apg,
            apg <= pg,
            apg <= TG_minG,
        ]

        problem = cp.Problem(cp.Minimize(obj), cons)
        solve_with_fallback(problem, mip=False)
        lambda_p = cons[0].dual_value
        mu_upper = cons[1].dual_value
        mu_lower = cons[2].dual_value
        if lambda_p is None or mu_upper is None or mu_lower is None:
            raise RuntimeError("LMP dual values are unavailable from the OPF solve.")
        lmp[t, :] = -lambda_p + PTDF.T @ (mu_upper - mu_lower)
        carbon_t = float(TG_carbon @ (pg.value - apg.value))
        carbon += carbon_t
        carbon_list.append(carbon_t)
        pg_rows.append(pg.value)
        apg_rows.append(apg.value)
        rg_rows.append(rg.value)

    result = {
        "carbon": carbon,
        "carbon_list": np.asarray(carbon_list),
        "LMP": lmp,
        "PG": np.asarray(pg_rows),
        "APG": np.asarray(apg_rows),
        "RG": np.asarray(rg_rows),
    }
    _write_lmp_result(case_tag, result)
    return result


def optimize_price_taking_storage(case_tag, T, prices, ES_ramp, ES_P, eff):
    es_count = len(ES_ramp)
    charge = cp.Variable((T, es_count), nonneg=True)
    discharge = cp.Variable((T, es_count), nonneg=True)
    soc = cp.Variable((T, es_count), nonneg=True)
    mode = cp.Variable((T, es_count), boolean=True)

    cons = [
        charge <= ES_ramp.reshape(1, -1),
        discharge <= ES_ramp.reshape(1, -1),
        soc <= ES_P.reshape(1, -1),
        charge <= cp.multiply(1 - mode, ES_ramp.reshape(1, -1)),
        discharge <= cp.multiply(mode, ES_ramp.reshape(1, -1)),
        soc[0, :] == 0.5 * ES_P,
        soc[T - 1, :] == 0.5 * ES_P,
        soc[T - 1, :] + cp.multiply(eff, charge[T - 1, :]) - cp.multiply(1 / eff, discharge[T - 1, :]) == 0.5 * ES_P,
    ]
    for t in range(T - 1):
        cons += [
            soc[t + 1, :]
            == soc[t, :] + cp.multiply(eff, charge[t, :]) - cp.multiply(1 / eff, discharge[t, :])
        ]

    objective = cp.Maximize(cp.sum(cp.multiply(prices.T, discharge - charge)))
    problem = cp.Problem(objective, cons)
    solver = solve_with_fallback(problem, mip=True)
    penalty_charge = np.where(charge.value > 1e-3, 1e3, -1e10)
    bid_discharge = np.where(discharge.value > 1e-3, -1e3, 1e10)
    result = {
        "charge": charge.value,
        "discharge": discharge.value,
        "SOC": soc.value,
        "penalty_charge_matrix": penalty_charge,
        "bid_discharge_matrix": bid_discharge,
        "objective": float(problem.value),
        "solver": str(solver),
    }
    _write_storage_schedule(case_tag, result)
    return result


def solve_uc_with_storage(
    case_tag,
    T,
    TG_offer,
    TG_maxG,
    TG_minG,
    TG_ramp,
    T_on,
    T_off,
    RG_offer,
    RG_P,
    RG_cap,
    RG_ramp,
    D_P,
    branch_max,
    PTDF,
    A_TG,
    A_RG,
    A_D,
    A_ES,
    ES_ramp,
    ES_P,
    eff,
    penalty_charge_matrix,
    bid_discharge_matrix,
    TG_start_cost,
    TG_stop_cost,
    initial_u=None,
    load_shed_penalty=5000.0,
    renewable_curtailment_penalty=100.0,
    thermal_curtailment_penalty=200.0,
):
    tg_count = len(TG_maxG)
    rg_count = len(RG_P)
    d_count = D_P.shape[1]
    es_count = len(ES_ramp)

    PG = cp.Variable((T, tg_count))
    APG = cp.Variable((T, tg_count))
    RG = cp.Variable((T, rg_count))
    LS = cp.Variable((T, d_count))
    charge = cp.Variable((T, es_count), nonneg=True)
    discharge = cp.Variable((T, es_count), nonneg=True)
    SOC = cp.Variable((T, es_count), nonneg=True)
    mode = cp.Variable((T, es_count), boolean=True)
    u = cp.Variable((T, tg_count), boolean=True)
    y = cp.Variable((T, tg_count), boolean=True)
    z = cp.Variable((T, tg_count), boolean=True)
    PD = D_P - LS

    renewable_available = RG_cap * RG_P.reshape(1, -1)
    obj = (
        cp.sum(cp.multiply(TG_offer.reshape(1, -1), PG - APG))
        + thermal_curtailment_penalty * cp.sum(APG)
        + cp.sum(cp.multiply(RG_offer.reshape(1, -1), RG))
        + renewable_curtailment_penalty * cp.sum(renewable_available - RG)
        + load_shed_penalty * cp.sum(LS)
        - cp.sum(cp.multiply(penalty_charge_matrix, charge))
        + cp.sum(cp.multiply(bid_discharge_matrix, discharge))
    )
    if T > 1:
        obj += cp.sum(cp.multiply(TG_start_cost.reshape(1, -1), y[1:, :]))
        obj += cp.sum(cp.multiply(TG_stop_cost.reshape(1, -1), z[1:, :]))

    cons = []
    if initial_u is not None:
        initial_u = np.asarray(initial_u, dtype=float)
        cons += [
            y[0, :] - z[0, :] == u[0, :] - initial_u,
            y[0, :] <= 1 - initial_u,
            z[0, :] <= initial_u,
        ]

    for t in range(T):
        cons += [0 <= PD[t, :], PD[t, :] <= D_P[t, :]]
        cons += [
            cp.multiply(u[t, :], TG_minG) <= PG[t, :],
            PG[t, :] <= cp.multiply(u[t, :], TG_maxG),
            0 <= APG[t, :],
            APG[t, :] <= PG[t, :],
            APG[t, :] <= TG_minG,
            0 <= RG[t, :],
            RG[t, :] <= renewable_available[t, :],
            charge[t, :] <= ES_ramp,
            discharge[t, :] <= ES_ramp,
            charge[t, :] <= cp.multiply(1 - mode[t, :], ES_ramp),
            discharge[t, :] <= cp.multiply(mode[t, :], ES_ramp),
            0 <= SOC[t, :],
            SOC[t, :] <= ES_P,
        ]
        _commitment_constraints(cons, u, y, z, t, tg_count, T_on, T_off)

        if t > 0:
            cons += [y[t, :] - z[t, :] == u[t, :] - u[t - 1, :]]
            cons += [cp.abs(PG[t, :] - PG[t - 1, :]) <= TG_ramp]
            cons += [cp.abs(RG[t, :] - RG[t - 1, :]) <= RG_ramp]
            cons += [
                SOC[t, :]
                == SOC[t - 1, :]
                + cp.multiply(eff, charge[t - 1, :])
                - cp.multiply(1 / eff, discharge[t - 1, :])
            ]

        if t == 0 or t == T - 1:
            cons += [SOC[t, :] == 0.5 * ES_P]

        cons += [
            cp.sum(PG[t, :] - APG[t, :]) + cp.sum(RG[t, :]) + cp.sum(discharge[t, :])
            == cp.sum(PD[t, :]) + cp.sum(charge[t, :])
        ]
        net = (
            A_TG @ (PG[t, :] - APG[t, :])
            + A_RG @ RG[t, :]
            - A_D @ PD[t, :]
            + A_ES @ (discharge[t, :] - charge[t, :])
        )
        flow = PTDF @ net
        cons += [flow <= branch_max, flow >= -branch_max]

    cons += [
        SOC[T - 1, :] + cp.multiply(eff, charge[T - 1, :]) - cp.multiply(1 / eff, discharge[T - 1, :])
        == 0.5 * ES_P
    ]

    problem = cp.Problem(cp.Minimize(obj), cons)
    solver = solve_with_fallback(problem, mip=True)
    result = {
        "u": np.clip(np.round(u.value), 0, 1),
        "PG": PG.value,
        "APG": APG.value,
        "RG": RG.value,
        "PD": PD.value,
        "LS": LS.value,
        "charge": charge.value,
        "discharge": discharge.value,
        "s": charge.value - discharge.value,
        "e": SOC.value,
        "objective": float(problem.value),
        "solver": str(solver),
    }
    _write_dispatch_result(case_tag, "uc_with_es", result)
    return result


def _write_dispatch_result(case_tag, prefix, result):
    output_dir = BASE_DIR / "results"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{prefix}_{case_tag}.xlsx"
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        for key in ["u", "PG", "APG", "RG", "PD", "LS", "s", "e", "charge", "discharge"]:
            if key in result and result[key] is not None:
                pd.DataFrame(result[key]).to_excel(writer, sheet_name=key, index=False)
        pd.DataFrame([{"objective": result.get("objective"), "solver": result.get("solver")}]).to_excel(
            writer, sheet_name="meta", index=False
        )


def _write_lmp_result(case_tag, result):
    output_dir = BASE_DIR / "results"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"lmp_no_es_{case_tag}.xlsx"
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        pd.DataFrame(result["LMP"]).to_excel(writer, sheet_name="LMP", index=False)
        pd.DataFrame({"carbon_t": result["carbon_list"]}).to_excel(writer, sheet_name="carbon", index=False)
        pd.DataFrame(result["PG"]).to_excel(writer, sheet_name="PG", index=False)
        pd.DataFrame(result["APG"]).to_excel(writer, sheet_name="APG", index=False)
        pd.DataFrame(result["RG"]).to_excel(writer, sheet_name="RG", index=False)


def _write_storage_schedule(case_tag, result):
    output_dir = BASE_DIR / "results"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"storage_schedule_{case_tag}.xlsx"
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        pd.DataFrame(result["charge"]).to_excel(writer, sheet_name="charge", index=False)
        pd.DataFrame(result["discharge"]).to_excel(writer, sheet_name="discharge", index=False)
        pd.DataFrame(result["SOC"]).to_excel(writer, sheet_name="SOC", index=False)
        pd.DataFrame(result["penalty_charge_matrix"]).to_excel(writer, sheet_name="Charge_Bid", index=False)
        pd.DataFrame(result["bid_discharge_matrix"]).to_excel(writer, sheet_name="Discharge_Bid", index=False)
        pd.DataFrame([{"objective": result.get("objective"), "solver": result.get("solver")}]).to_excel(
            writer, sheet_name="meta", index=False
        )
