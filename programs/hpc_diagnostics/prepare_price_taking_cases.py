import argparse
import json
import os
import pickle
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

WORKFLOW_DIR = os.path.abspath(os.path.dirname(__file__))
MAIN_WORKFLOW_DIR = os.path.abspath(os.path.join(WORKFLOW_DIR, "..", "main_workflow"))
sys.path.append(WORKFLOW_DIR)
sys.path.append(MAIN_WORKFLOW_DIR)

from coalition_kernel_core import participant_labels, write_random_samples  # noqa: E402
from make_ieee14_uc_opf_es import ieee14_uc_opf_es_dict  # noqa: E402
from make_PTDF_es import PTDF  # noqa: E402
from opf_lmp_carbon import run_opf_carbon  # noqa: E402
from run_es_legacy import optimize_ess_schedule  # noqa: E402
from run_uc import uc  # noqa: E402
from run_uc_es import uc_es  # noqa: E402


DEFAULT_CASES = ("PT14_BASE_2h", "PT14_RG0x_8h", "PT14_RG2x_8h", "PT14_RG4x_8h")

CASE_CONFIG = {
    "PT14_BASE_2h": {
        "res_scale": 1.0,
        "duration_h": 2.0,
        "renewable_line_limit": None,
    },
    "PT14_RG0x_8h": {
        "res_scale": 0.0,
        "duration_h": 8.0,
        "renewable_line_limit": 200.0,
    },
    "PT14_RG2x_8h": {
        "res_scale": 2.0,
        "duration_h": 8.0,
        "renewable_line_limit": 200.0,
    },
    "PT14_RG4x_8h": {
        "res_scale": 4.0,
        "duration_h": 8.0,
        "renewable_line_limit": 200.0,
    },
}


def apply_renewable_line_relaxation(case, limit_mw):
    if limit_mw is None:
        return case
    case["branch"] = case["branch"].astype(float).copy()
    renewable_buses = set(case["RG_bl"].astype(int).tolist())
    for row in case["branch"]:
        f_bus, t_bus = int(row[0]), int(row[1])
        if f_bus in renewable_buses or t_bus in renewable_buses:
            row[3] = float(limit_mw)
    return case


def build_price_taking_case(config, sceneid=3):
    case = ieee14_uc_opf_es_dict(sceneid)
    case = {k: np.asarray(v).copy() if isinstance(v, np.ndarray) else v for k, v in case.items()}

    base_rg_power = case["RG_P"].astype(float).copy()
    case["RG_P"] = base_rg_power * float(config["res_scale"])
    case["RG_ramp"] = np.maximum(case["RG_P"].astype(float), 1e-6)
    case["ES_P"] = case["ES_ramp"].astype(float) * float(config["duration_h"])
    case = apply_renewable_line_relaxation(case, config.get("renewable_line_limit"))
    return case


def split_storage_roles(tag, case_es, uc_es_result, p_charge, p_discharge):
    n_es = int(case_es["ES_num"])
    n_rg = int(case_es["RG_num"])
    n_d = int(case_es["D_num"])

    split_case = {
        "sceneid": str(tag),
        "T": int(case_es["T"]),
        "TG_num": int(case_es["TG_num"]),
        "RG_num": int(n_rg + n_es),
        "D_num": int(n_d + n_es),
        "ES_num": n_es,
        "real_RG_num": n_rg,
        "real_D_num": n_d,
        "bus_num": int(case_es["bus_num"]),
        "branch_num": int(case_es["branch_num"]),
        "TG_bl": case_es["TG_bl"].astype(int),
        "TG_offer": case_es["TG_offer"].astype(float),
        "TG_carbon": case_es["TG_carbon"].astype(float),
        "TG_maxG": case_es["TG_maxG"].astype(float),
        "TG_minG": case_es["TG_minG"].astype(float),
        "TG_ramp": case_es["TG_ramp"].astype(float),
        "T_on": case_es["T_on"].astype(int),
        "T_off": case_es["T_off"].astype(int),
        "u_TG": uc_es_result["u"].astype(int),
        "RG_bl": np.hstack([case_es["RG_bl"].astype(int), case_es["ES_bl"].astype(int)]),
        "RG_offer": np.hstack([case_es["RG_offer"].astype(float), np.zeros(n_es)]),
        "RG_P": np.hstack([case_es["RG_P"].astype(float), np.ones(n_es)]),
        "RG_ramp": np.hstack([case_es["RG_ramp"].astype(float), case_es["ES_ramp"].astype(float)]),
        "RG_cap": np.hstack([case_es["RG_cap"].astype(float), p_discharge]),
        "D_bl": np.hstack([case_es["D_bl"].astype(int), case_es["ES_bl"].astype(int)]),
        "D_P": np.hstack([case_es["D_P"].astype(float), p_charge]),
        "branch": case_es["branch"].astype(float),
        "ES_bl": case_es["ES_bl"].astype(int),
        "ES_ramp": case_es["ES_ramp"].astype(float),
        "ES_P": case_es["ES_P"].astype(float),
        "p_charge": p_charge.astype(float),
        "p_discharge": p_discharge.astype(float),
        "SOC": uc_es_result["e"].astype(float),
        "load_shed_penalty": 5000.0,
        "renewable_curtailment_penalty": 100.0,
        "thermal_curtailment_penalty": 200.0,
        "trajectory_model": "LMP-based price-taking ESS self-schedule",
        "storage_split_note": "ESS discharging roles use realized p_discharge as time-varying available generation; ESS charging roles use realized p_charge as time-varying demand.",
    }
    return split_case


def dispatch_summary(case, uc_no_es_result, uc_with_es_result, tag, config):
    available = case["RG_cap"].astype(float) * case["RG_P"].astype(float).reshape(1, -1)
    no_es_curtailment = np.maximum(available - uc_no_es_result["RG"], 0.0)
    with_es_curtailment = np.maximum(available - uc_with_es_result["RG"], 0.0)
    p_charge = np.maximum(uc_with_es_result["s"], 0.0)
    p_discharge = -np.minimum(uc_with_es_result["s"], 0.0)
    no_es_net_thermal = uc_no_es_result["PG"] - uc_no_es_result["APG"]
    with_es_net_thermal = uc_with_es_result["PG"] - uc_with_es_result["APG"]
    no_es_carbon = np.sum(no_es_net_thermal * case["TG_carbon"].astype(float).reshape(1, -1))
    with_es_carbon = np.sum(with_es_net_thermal * case["TG_carbon"].astype(float).reshape(1, -1))
    load_energy = float(np.sum(case["D_P"]))
    load_peak = float(np.max(np.sum(case["D_P"], axis=1)))
    renewable_used = float(np.sum(uc_with_es_result["RG"]))
    thermal_used = float(np.sum(with_es_net_thermal))
    total_rg_capacity = float(np.sum(case["RG_P"]))

    return {
        "scenario": tag,
        "trajectory_model": "price-taking",
        "res_scale": float(config["res_scale"]),
        "duration_h": float(config["duration_h"]),
        "T": int(case["T"]),
        "load_energy_MWh": load_energy,
        "load_peak_MW": load_peak,
        "total_RG_capacity_MW": total_rg_capacity,
        "RG_capacity_to_peak_load_pct": float(100 * total_rg_capacity / load_peak) if load_peak else 0.0,
        "total_ES_power_MW": float(np.sum(case["ES_ramp"])),
        "total_ES_energy_MWh": float(np.sum(case["ES_P"])),
        "ES_power_to_peak_load_pct": float(100 * np.sum(case["ES_ramp"]) / load_peak) if load_peak else 0.0,
        "renewable_available_MWh": float(np.sum(available)),
        "renewable_used_MWh": renewable_used,
        "renewable_used_to_load_pct": float(100 * renewable_used / load_energy) if load_energy else 0.0,
        "actual_RES_penetration_pct": float(100 * renewable_used / (renewable_used + thermal_used))
        if renewable_used + thermal_used > 1e-12 else 0.0,
        "curtailment_MWh": float(np.sum(with_es_curtailment)),
        "curtailment_rate_pct": float(100 * np.sum(with_es_curtailment) / np.sum(available))
        if np.sum(available) > 1e-12 else 0.0,
        "thermal_generation_MWh": thermal_used,
        "load_shedding_MWh": float(np.sum(uc_with_es_result["LS"])),
        "carbon_tCO2": float(with_es_carbon),
        "charge_MWh": float(np.sum(p_charge)),
        "discharge_MWh": float(np.sum(p_discharge)),
        "throughput_MWh": float(np.sum(p_charge + p_discharge)),
        "no_ES_renewable_used_MWh": float(np.sum(uc_no_es_result["RG"])),
        "no_ES_curtailment_MWh": float(np.sum(no_es_curtailment)),
        "no_ES_curtailment_rate_pct": float(100 * np.sum(no_es_curtailment) / np.sum(available))
        if np.sum(available) > 1e-12 else 0.0,
        "no_ES_load_shedding_MWh": float(np.sum(uc_no_es_result["LS"])),
        "no_ES_carbon_tCO2": float(no_es_carbon),
        "delta_curtailment_MWh_with_minus_noES": float(np.sum(with_es_curtailment) - np.sum(no_es_curtailment)),
        "delta_carbon_tCO2_with_minus_noES": float(with_es_carbon - no_es_carbon),
    }


def prepare_one(tag, args):
    config = CASE_CONFIG[tag]
    case = build_price_taking_case(config, sceneid=args.sceneid)
    ptdf_data = PTDF(case)
    initial_u = np.ones(int(case["TG_num"]))
    start_cost = case.get("TG_start_cost", np.zeros(int(case["TG_num"]))).astype(float)
    stop_cost = case.get("TG_stop_cost", np.zeros(int(case["TG_num"]))).astype(float)

    uc_no_es = uc(
        tag + "_noES",
        case["T"],
        case["TG_offer"].astype(float),
        case["TG_maxG"].astype(float),
        case["TG_minG"].astype(float),
        case["TG_ramp"].astype(float),
        case["T_on"].astype(int),
        case["T_off"].astype(int),
        case["RG_offer"].astype(float),
        case["RG_P"].astype(float),
        case["RG_cap"].astype(float),
        case["RG_ramp"].astype(float),
        case["D_P"].astype(float),
        ptdf_data["branch_max"],
        ptdf_data["PTDF"],
        ptdf_data["A_TG"],
        ptdf_data["A_RG"],
        ptdf_data["A_D"],
        start_cost,
        stop_cost,
        initial_u=initial_u,
    )

    lmp_result = run_opf_carbon(
        tag + "_noES",
        case["T"],
        uc_no_es["u"],
        case["TG_carbon"].astype(float),
        case["TG_offer"].astype(float),
        case["TG_maxG"].astype(float),
        case["TG_minG"].astype(float),
        case["RG_offer"].astype(float),
        case["RG_P"].astype(float),
        case["RG_cap"].astype(float),
        case["D_P"].astype(float),
        ptdf_data["branch_max"],
        ptdf_data["PTDF"],
        ptdf_data["A_TG"],
        ptdf_data["A_RG"],
        ptdf_data["A_D"],
        int(case["D_num"]),
    )
    prices = (lmp_result["LMP"] @ ptdf_data["A_ES"]).T
    ess_result = optimize_ess_schedule(
        case["T"],
        prices,
        tag,
        int(case["ES_num"]),
        case["ES_ramp"].astype(float),
        case["ES_P"].astype(float),
        case["eff"].astype(float),
    )

    uc_with_es = uc_es(
        tag,
        case["T"],
        case["TG_offer"].astype(float),
        case["TG_maxG"].astype(float),
        case["TG_minG"].astype(float),
        case["TG_ramp"].astype(float),
        case["T_on"].astype(int),
        case["T_off"].astype(int),
        case["RG_offer"].astype(float),
        case["RG_P"].astype(float),
        case["RG_cap"].astype(float),
        case["RG_ramp"].astype(float),
        case["D_P"].astype(float),
        ptdf_data["branch_max"],
        ptdf_data["PTDF"],
        ptdf_data["A_TG"],
        ptdf_data["A_RG"],
        ptdf_data["A_D"],
        ptdf_data["A_ES"],
        case["ES_ramp"].astype(float),
        case["ES_P"].astype(float),
        case["eff"].astype(float),
        ess_result["penalty_charge_matrix"],
        ess_result["bid_discharge_matrix"],
        start_cost,
        stop_cost,
        initial_u=initial_u,
    )

    p_charge = np.maximum(uc_with_es["s"], 0.0)
    p_discharge = -np.minimum(uc_with_es["s"], 0.0)
    p_discharge[p_discharge == -0.0] = 0.0
    split_case = split_storage_roles(tag, case, uc_with_es, p_charge, p_discharge)

    data_dir = os.path.join(WORKFLOW_DIR, "data")
    random_dir = os.path.join(WORKFLOW_DIR, "random_S_set", tag)
    os.makedirs(data_dir, exist_ok=True)
    case_path = os.path.join(data_dir, f"case_example_dict_{tag}.pkl")
    with open(case_path, "wb") as f:
        pickle.dump(split_case, f)

    n_agents = int(split_case["TG_num"] + split_case["RG_num"] + split_case["D_num"])
    write_random_samples(random_dir, n_agents, args.kernel_num, args.samples_per_kernel, args.seed)

    summary = dispatch_summary(case, uc_no_es, uc_with_es, tag, config)
    metadata = {
        "experiment": "ieee14_price_taking_cases",
        "case_tag": tag,
        "case_path": case_path,
        "n_agents_origin": n_agents,
        "n_agents_merged": len(participant_labels(split_case)) - int(split_case["ES_num"]),
        "participant_labels_origin": participant_labels(split_case),
        "kernel_num": int(args.kernel_num),
        "samples_per_kernel": int(args.samples_per_kernel),
        "random_seed": int(args.seed),
        "sceneid": str(args.sceneid),
        "case_config": config,
        "uc_note": "Thermal UC uses corrected startup/shutdown logic with initial units online.",
        "storage_split_note": split_case["storage_split_note"],
        "dispatch_summary": summary,
    }
    with open(os.path.join(data_dir, f"metadata_{tag}.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    pd.DataFrame(uc_no_es["u"]).to_csv(os.path.join(data_dir, f"UC_noES_{tag}.csv"), index=False)
    pd.DataFrame(uc_with_es["u"]).to_csv(os.path.join(data_dir, f"UC_{tag}.csv"), index=False)
    pd.DataFrame(uc_with_es["PG"]).to_csv(os.path.join(data_dir, f"PG_{tag}.csv"), index=False)
    pd.DataFrame(uc_with_es["APG"]).to_csv(os.path.join(data_dir, f"APG_{tag}.csv"), index=False)
    pd.DataFrame(uc_with_es["RG"]).to_csv(os.path.join(data_dir, f"RG_{tag}.csv"), index=False)
    pd.DataFrame(uc_with_es["LS"]).to_csv(os.path.join(data_dir, f"LS_{tag}.csv"), index=False)
    pd.DataFrame(uc_with_es["e"]).to_csv(os.path.join(data_dir, f"SOC_{tag}.csv"), index=False)
    pd.DataFrame(p_charge).to_csv(os.path.join(data_dir, f"charge_{tag}.csv"), index=False)
    pd.DataFrame(p_discharge).to_csv(os.path.join(data_dir, f"discharge_{tag}.csv"), index=False)
    return summary


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare IEEE14 price-taking cases.")
    parser.add_argument("--cases", nargs="+", default=list(DEFAULT_CASES), choices=list(CASE_CONFIG))
    parser.add_argument("--sceneid", type=int, default=3)
    parser.add_argument("--kernel-num", type=int, default=1000)
    parser.add_argument("--samples-per-kernel", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1126)
    return parser.parse_args()


def main():
    args = parse_args()
    os.makedirs(os.path.join(WORKFLOW_DIR, "data"), exist_ok=True)
    summaries = [prepare_one(tag, args) for tag in args.cases]
    summary_df = pd.DataFrame(summaries)
    output_path = os.path.join(WORKFLOW_DIR, "data", "prepared_ieee14_price_taking_summary.xlsx")
    summary_df.to_excel(output_path, index=False)
    summary_df.to_csv(os.path.join(WORKFLOW_DIR, "data", "prepared_ieee14_price_taking_summary.csv"), index=False)
    print("Prepared IEEE14 price-taking cases:", output_path)
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
