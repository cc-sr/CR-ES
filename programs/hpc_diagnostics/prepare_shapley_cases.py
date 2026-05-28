import argparse
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

HPC_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(HPC_DIR)

from coalition_kernel_core import participant_labels, write_random_samples  # noqa: E402
from ieee14_dispatch_model import (  # noqa: E402
    apply_current_high_renewable_branch_limits,
    build_latest_params,
    load_case_with_data_file,
    solve_lmp_fixed_uc_storage,
    solve_uc_endogenous_storage,
)


DEFAULT_STORAGE_SCENARIOS = {
    "ES40_30MW": (40.0, 30.0),
    "ES80_60MW": (80.0, 60.0),
    "ES130_110MW": (130.0, 110.0),
}

RENEWABLE_SENSITIVITY_ES = (40.0, 30.0)
RENEWABLE_TARGET_CAPACITY_TO_PEAK = [0.0, 2.0, 3.0]
BASE_RENEWABLE_CAPACITY = np.array([580.0, 260.0, 190.0])
COAL_CAPACITY_MW = 300.0


def rounded_capacity_by_target_ratio(load_peak, target_ratio):
    if target_ratio <= 0:
        return np.zeros_like(BASE_RENEWABLE_CAPACITY)
    target_total = round(target_ratio * load_peak / 10.0) * 10.0
    raw = BASE_RENEWABLE_CAPACITY / BASE_RENEWABLE_CAPACITY.sum() * target_total
    caps = np.round(raw / 10.0) * 10.0
    diff = target_total - caps.sum()
    if abs(diff) > 1e-9:
        caps[np.argmax(BASE_RENEWABLE_CAPACITY)] += diff
    return caps.astype(float)


def renewable_scenarios(load_peak):
    es1, es2 = RENEWABLE_SENSITIVITY_ES
    scenarios = {}
    for target_ratio in RENEWABLE_TARGET_CAPACITY_TO_PEAK:
        tag = f"RGcap{target_ratio:g}xPeak_ES{int(es1)}_{int(es2)}MW"
        scenarios[tag] = (es1, es2, rounded_capacity_by_target_ratio(load_peak, target_ratio))
    return scenarios


def build_split_storage_case(params, base_case, uc_result):
    n_es = int(base_case["ES_num"])
    n_rg = int(base_case["RG_num"])
    n_d = int(base_case["D_num"])

    branch = base_case["branch"].astype(float).copy()
    branch[:, 3] = params["branch_max"]

    p_charge = np.maximum(uc_result["p_charge"], 0.0)
    p_discharge = np.maximum(uc_result["p_discharge"], 0.0)

    case = {
        "T": int(params["T"]),
        "TG_num": int(base_case["TG_num"]),
        "RG_num": int(n_rg + n_es),
        "D_num": int(n_d + n_es),
        "ES_num": n_es,
        "real_RG_num": n_rg,
        "real_D_num": n_d,
        "bus_num": int(base_case["bus_num"]),
        "branch_num": int(base_case["branch_num"]),
        "TG_bl": base_case["TG_bl"].astype(int),
        "TG_offer": params["TG_offer"].astype(float),
        "TG_carbon": params["TG_carbon"].astype(float),
        "TG_maxG": params["TG_maxG"].astype(float),
        "TG_minG": params["TG_minG"].astype(float),
        "TG_ramp": params["TG_ramp"].astype(float),
        "T_on": params["T_on"].astype(int),
        "T_off": params["T_off"].astype(int),
        "u_TG": uc_result["u"].astype(int),
        "RG_bl": np.hstack([base_case["RG_bl"].astype(int), base_case["ES_bl"].astype(int)]),
        "RG_offer": np.hstack([params["RG_offer"].astype(float), np.zeros(n_es)]),
        "RG_P": np.hstack([params["RG_P"].astype(float), np.ones(n_es)]),
        "RG_ramp": np.hstack([params["RG_ramp"].astype(float), params["ES_ramp"].astype(float)]),
        "RG_cap": np.hstack([params["RG_cap"].astype(float), p_discharge]),
        "D_bl": np.hstack([base_case["D_bl"].astype(int), base_case["ES_bl"].astype(int)]),
        "D_P": np.hstack([params["D_P"].astype(float), p_charge]),
        "branch": branch,
        "ES_bl": base_case["ES_bl"].astype(int),
        "ES_ramp": params["ES_ramp"].astype(float),
        "ES_P": params["ES_P"].astype(float),
        "p_charge": p_charge,
        "p_discharge": p_discharge,
        "SOC": uc_result["soc"].astype(float),
        "load_shed_penalty": float(params["load_shed_penalty"]),
        "renewable_curtailment_penalty": float(params["renewable_curtailment_penalty"]),
        "thermal_curtailment_penalty": float(params["thermal_curtailment_penalty"]),
    }
    return case


def summarize_dispatch(tag, params, uc_result, lmp_result):
    available = params["RG_cap"] * params["RG_P"]
    curtailment = np.maximum(available - uc_result["RG"], 0.0)
    return {
        "scenario": tag,
        "T": int(params["T"]),
        "load_peak_MW": float(params["load_peak"]),
        "load_energy_MWh": float(params["load_energy"]),
        "total_RG_capacity_MW": float(np.sum(params["RG_P"])),
        "total_ES_power_MW": float(np.sum(params["ES_ramp"])),
        "total_ES_energy_MWh": float(np.sum(params["ES_P"])),
        "ES_power_to_peak_load_pct": float(100 * np.sum(params["ES_ramp"]) / params["load_peak"]),
        "renewable_available_MWh": float(np.sum(available)),
        "renewable_used_MWh": float(np.sum(uc_result["RG"])),
        "curtailment_MWh": float(np.sum(curtailment)),
        "thermal_generation_MWh": float(np.sum(lmp_result["PG"])),
        "load_shedding_MWh": float(np.sum(uc_result["LS"])),
        "carbon_tCO2": float(np.sum(lmp_result["carbon"])),
        "charge_MWh": float(np.sum(uc_result["p_charge"])),
        "discharge_MWh": float(np.sum(uc_result["p_discharge"])),
        "throughput_MWh": float(np.sum(uc_result["p_charge"] + uc_result["p_discharge"])),
    }


def prepare_one(
    tag,
    es1_mw,
    es2_mw,
    duration_h,
    days,
    max_kernel_num,
    samples_per_kernel,
    seed,
    experiment,
    renewable_capacity=None,
    network_capacity_scale=2.0,
):
    base_case = load_case_with_data_file(
        "ieee14_profile_data.xlsx",
        resource_layout="retyped_13wind_2solar_68_thermal",
        ess_layout="original",
    )
    params = build_latest_params(es1_mw, es2_mw, duration_h, days)
    apply_current_high_renewable_branch_limits(params, base_case)
    params["TG_maxG"][1] = COAL_CAPACITY_MW
    params["TG_ramp"][1] = 0.6 * COAL_CAPACITY_MW
    params["branch_max"] = params["branch_max"] * float(network_capacity_scale)
    if renewable_capacity is not None:
        params["RG_P"] = np.asarray(renewable_capacity, dtype=float)
        params["RG_ramp"] = np.asarray(renewable_capacity, dtype=float)
        params["renewable_available_energy"] = float(np.sum(params["RG_cap"] * params["RG_P"]))
    params["initial_u"] = np.ones(len(params["TG_maxG"]))
    params["degradation_cost"] = 5.0

    uc_result = solve_uc_endogenous_storage(params, degradation_cost=params["degradation_cost"])
    lmp_result = solve_lmp_fixed_uc_storage(params, uc_result["u"], uc_result["p_charge"], uc_result["p_discharge"])

    split_case = build_split_storage_case(params, base_case, uc_result)
    case_dir = os.path.join(HPC_DIR, "data")
    random_dir = os.path.join(HPC_DIR, "random_S_set", tag)
    os.makedirs(case_dir, exist_ok=True)

    case_path = os.path.join(case_dir, f"case_example_dict_{tag}.pkl")
    with open(case_path, "wb") as f:
        pickle.dump(split_case, f)

    n_agents = int(split_case["TG_num"] + split_case["RG_num"] + split_case["D_num"])
    write_random_samples(random_dir, n_agents, max_kernel_num, samples_per_kernel, seed)

    summary = summarize_dispatch(tag, params, uc_result, lmp_result)
    metadata = {
        "experiment": experiment,
        "case_tag": tag,
        "case_path": case_path,
        "n_agents_origin": n_agents,
        "n_agents_merged": len(participant_labels(split_case)) - int(split_case["ES_num"]),
        "participant_labels_origin": participant_labels(split_case),
        "max_kernel_num": int(max_kernel_num),
        "samples_per_kernel": int(samples_per_kernel),
        "random_seed": int(seed),
        "duration_h": float(duration_h),
        "days": int(days),
        "network_capacity_scale": float(network_capacity_scale),
        "renewable_capacity_MW": params["RG_P"].astype(float).tolist(),
        "dispatch_summary": summary,
    }
    with open(os.path.join(case_dir, f"metadata_{tag}.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return summary


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare realized IEEE14 high-renewable cases for HPC KernelSHAP.")
    parser.add_argument(
        "--experiment",
        choices=["storage", "renewable", "all-required"],
        default="storage",
        help="Case set to prepare: storage sensitivity, renewable sensitivity, or both.",
    )
    parser.add_argument("--scenario", default="all", help="Scenario tag, or 'all'.")
    parser.add_argument("--duration-h", type=float, default=4.0)
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--renewable-days", type=int, default=1)
    parser.add_argument("--max-kernel-num", type=int, default=1000)
    parser.add_argument("--samples-per-kernel", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1126)
    parser.add_argument("--network-capacity-scale", type=float, default=2.0)
    return parser.parse_args()


def main():
    args = parse_args()
    storage_days = 3 if args.days is None else int(args.days)
    renewable_days = int(args.renewable_days if args.days is None else args.days)

    probe = build_latest_params(
        RENEWABLE_SENSITIVITY_ES[0],
        RENEWABLE_SENSITIVITY_ES[1],
        duration_h=args.duration_h,
        days=1,
    )
    renewable_defaults = renewable_scenarios(probe["load_peak"])

    case_queue = []
    if args.experiment in ("storage", "all-required"):
        if args.scenario == "all" or args.experiment == "all-required":
            storage_cases = DEFAULT_STORAGE_SCENARIOS
        else:
            if args.scenario not in DEFAULT_STORAGE_SCENARIOS:
                raise ValueError(
                    f"Unknown storage scenario {args.scenario}. "
                    f"Available: {', '.join(DEFAULT_STORAGE_SCENARIOS)}"
                )
            storage_cases = {args.scenario: DEFAULT_STORAGE_SCENARIOS[args.scenario]}
        for tag, (es1, es2) in storage_cases.items():
            case_queue.append(("storage", tag, es1, es2, None, storage_days))

    if args.experiment in ("renewable", "all-required"):
        if args.scenario == "all" or args.experiment == "all-required":
            rg_cases = renewable_defaults
        else:
            if args.scenario not in renewable_defaults:
                raise ValueError(
                    f"Unknown renewable scenario {args.scenario}. "
                    f"Available: {', '.join(renewable_defaults)}"
                )
            rg_cases = {args.scenario: renewable_defaults[args.scenario]}
        for tag, (es1, es2, rg_capacity) in rg_cases.items():
            case_queue.append(("renewable", tag, es1, es2, rg_capacity, renewable_days))

    summaries = []
    for experiment, tag, es1, es2, rg_capacity, days in case_queue:
        if rg_capacity is None:
            print(f"Preparing {tag}: ES1={es1} MW, ES2={es2} MW, days={days}")
        else:
            print(
                f"Preparing {tag}: ES1={es1} MW, ES2={es2} MW, "
                f"RG={rg_capacity.tolist()} MW, days={days}"
            )
        summaries.append(
            prepare_one(
                tag,
                es1,
                es2,
                args.duration_h,
                days,
                args.max_kernel_num,
                args.samples_per_kernel,
                args.seed,
                experiment,
                renewable_capacity=rg_capacity,
                network_capacity_scale=args.network_capacity_scale,
            )
        )

    summary_df = pd.DataFrame(summaries)
    if args.experiment == "all-required":
        output_name = "prepared_ieee14_required_case_summary.xlsx"
    else:
        output_name = f"prepared_ieee14_{args.experiment}_case_summary.xlsx"
    output_path = os.path.join(HPC_DIR, "data", output_name)
    summary_df.to_excel(output_path, index=False)
    summary_df.to_excel(os.path.join(HPC_DIR, "data", "prepared_case_summary.xlsx"), index=False)
    print("Prepared case summary:", output_path)
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
