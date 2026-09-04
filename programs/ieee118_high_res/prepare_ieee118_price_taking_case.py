import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from ieee118_case_builder import (  # noqa: E402
    DEFAULT_CASE118_PATH,
    DEFAULT_PROFILE_PATH,
    build_ieee118_price_taking_case,
    to_jsonable,
    write_case_settings,
)


def split_storage_roles(case, uc_with_es, p_charge, p_discharge):
    n_es = int(case["ES_num"])
    n_rg = int(case["RG_num"])
    n_d = int(case["D_num"])
    return {
        "sceneid": str(case["case_tag"]),
        "T": int(case["T"]),
        "TG_num": int(case["TG_num"]),
        "RG_num": int(n_rg + n_es),
        "D_num": int(n_d + n_es),
        "ES_num": n_es,
        "real_RG_num": n_rg,
        "real_D_num": n_d,
        "bus_num": int(case["bus_num"]),
        "branch_num": int(case["branch_num"]),
        "TG_bl": case["TG_bl"].astype(int),
        "TG_offer": case["TG_offer"].astype(float),
        "TG_carbon": case["TG_carbon"].astype(float),
        "TG_maxG": case["TG_maxG"].astype(float),
        "TG_minG": case["TG_minG"].astype(float),
        "TG_ramp": case["TG_ramp"].astype(float),
        "TG_start_cost": case["TG_start_cost"].astype(float),
        "TG_stop_cost": case["TG_stop_cost"].astype(float),
        "T_on": case["T_on"].astype(int),
        "T_off": case["T_off"].astype(int),
        "u_TG": uc_with_es["u"].astype(int),
        "RG_bl": np.hstack([case["RG_bl"].astype(int), case["ES_bl"].astype(int)]),
        "RG_offer": np.hstack([case["RG_offer"].astype(float), np.zeros(n_es)]),
        "RG_P": np.hstack([case["RG_P"].astype(float), np.ones(n_es)]),
        "RG_ramp": np.hstack([case["RG_ramp"].astype(float), case["ES_ramp"].astype(float)]),
        "RG_cap": np.hstack([case["RG_cap"].astype(float), p_discharge.astype(float)]),
        "D_bl": np.hstack([case["D_bl"].astype(int), case["ES_bl"].astype(int)]),
        "D_P": np.hstack([case["D_P"].astype(float), p_charge.astype(float)]),
        "branch": case["branch"].astype(float),
        "ES_bl": case["ES_bl"].astype(int),
        "ES_ramp": case["ES_ramp"].astype(float),
        "ES_P": case["ES_P"].astype(float),
        "p_charge": p_charge.astype(float),
        "p_discharge": p_discharge.astype(float),
        "SOC": uc_with_es["e"].astype(float),
        "load_shed_penalty": float(case["load_shed_penalty"]),
        "renewable_curtailment_penalty": float(case["renewable_curtailment_penalty"]),
        "thermal_curtailment_penalty": float(case["thermal_curtailment_penalty"]),
        "trajectory_model": "LMP-based price-taking ESS self-schedule",
        "storage_split_note": (
            "ESS discharging roles use realized p_discharge as time-varying available "
            "generation with RG_P=1; ESS charging roles use realized p_charge as "
            "time-varying demand."
        ),
    }


def dispatch_summary(case, uc_no_es, uc_with_es):
    available = case["RG_cap"].astype(float) * case["RG_P"].astype(float).reshape(1, -1)
    no_es_curtailment = np.maximum(available - uc_no_es["RG"], 0.0)
    with_es_curtailment = np.maximum(available - uc_with_es["RG"], 0.0)
    p_charge = np.maximum(uc_with_es["s"], 0.0)
    p_discharge = -np.minimum(uc_with_es["s"], 0.0)
    no_es_net_thermal = uc_no_es["PG"] - uc_no_es["APG"]
    with_es_net_thermal = uc_with_es["PG"] - uc_with_es["APG"]
    no_es_carbon = np.sum(no_es_net_thermal * case["TG_carbon"].astype(float).reshape(1, -1))
    with_es_carbon = np.sum(with_es_net_thermal * case["TG_carbon"].astype(float).reshape(1, -1))
    load_energy = float(np.sum(case["D_P"]))
    load_peak = float(np.max(np.sum(case["D_P"], axis=1)))
    renewable_used = float(np.sum(uc_with_es["RG"]))
    thermal_used = float(np.sum(with_es_net_thermal))

    return {
        "scenario": str(case["case_tag"]),
        "trajectory_model": "price-taking",
        "T": int(case["T"]),
        "TG_num": int(case["TG_num"]),
        "RG_num": int(case["RG_num"]),
        "D_num": int(case["D_num"]),
        "ES_num": int(case["ES_num"]),
        "origin_agent_count_before_ess_recombination": int(
            case["TG_num"] + case["RG_num"] + case["D_num"] + 2 * case["ES_num"]
        ),
        "merged_agent_count_after_ess_recombination": int(
            case["TG_num"] + case["RG_num"] + case["D_num"] + case["ES_num"]
        ),
        "load_energy_MWh": load_energy,
        "load_peak_MW": load_peak,
        "thermal_capacity_MW": float(np.sum(case["TG_maxG"])),
        "renewable_capacity_MW": float(np.sum(case["RG_P"])),
        "renewable_capacity_to_peak_load_pct": float(100 * np.sum(case["RG_P"]) / load_peak),
        "total_ES_power_MW": float(np.sum(case["ES_ramp"])),
        "total_ES_energy_MWh": float(np.sum(case["ES_P"])),
        "ES_power_to_peak_load_pct": float(100 * np.sum(case["ES_ramp"]) / load_peak),
        "renewable_available_MWh": float(np.sum(available)),
        "renewable_used_MWh": renewable_used,
        "renewable_used_to_load_pct": float(100 * renewable_used / load_energy) if load_energy else 0.0,
        "actual_RES_penetration_pct": float(100 * renewable_used / (renewable_used + thermal_used))
        if renewable_used + thermal_used > 1e-12
        else 0.0,
        "curtailment_MWh": float(np.sum(with_es_curtailment)),
        "curtailment_rate_pct": float(100 * np.sum(with_es_curtailment) / np.sum(available))
        if np.sum(available) > 1e-12
        else 0.0,
        "thermal_generation_MWh": thermal_used,
        "load_shedding_MWh": float(np.sum(uc_with_es["LS"])),
        "carbon_tCO2": float(with_es_carbon),
        "charge_MWh": float(np.sum(p_charge)),
        "discharge_MWh": float(np.sum(p_discharge)),
        "throughput_MWh": float(np.sum(p_charge + p_discharge)),
        "no_ES_renewable_used_MWh": float(np.sum(uc_no_es["RG"])),
        "no_ES_curtailment_MWh": float(np.sum(no_es_curtailment)),
        "no_ES_load_shedding_MWh": float(np.sum(uc_no_es["LS"])),
        "no_ES_carbon_tCO2": float(no_es_carbon),
        "delta_curtailment_MWh_with_minus_noES": float(
            np.sum(with_es_curtailment) - np.sum(no_es_curtailment)
        ),
        "delta_carbon_tCO2_with_minus_noES": float(with_es_carbon - no_es_carbon),
        "uc_no_es_solver": uc_no_es.get("solver"),
        "uc_with_es_solver": uc_with_es.get("solver"),
    }


def prepare_case(args):
    case = build_ieee118_price_taking_case(
        case_tag=args.case_tag,
        case118_path=args.case118_path,
        profile_path=args.profile_path,
        days=args.days,
        day_of_interest=args.day_of_interest,
        load_scale=args.load_scale,
        renewable_buses=args.renewable_buses,
        renewable_capacity_reference_buses=args.renewable_capacity_reference_buses,
        renewable_capacity_to_peak=args.renewable_capacity_to_peak,
        ess_buses=args.ess_buses,
        ess_power_to_peak=args.ess_power_to_peak,
        ess_duration_h=args.ess_duration_h,
        branch_limit_mw=args.branch_limit_mw,
        branch_limit_overrides=args.branch_limit_overrides,
        coal_capacity_scale=args.coal_capacity_scale,
        gas_capacity_scale=args.gas_capacity_scale,
        capacity_rounding_mw=args.capacity_rounding_mw,
        random_seed=args.seed,
    )

    if int(args.smoke_hours) < int(case["T"]):
        smoke_hours = max(1, int(args.smoke_hours))
        case["T"] = smoke_hours
        case["D_P"] = case["D_P"][:smoke_hours]
        case["RG_cap"] = case["RG_cap"][:smoke_hours]
        case["metadata"]["hours"] = smoke_hours
        case["metadata"]["load_energy_MWh"] = float(np.sum(case["D_P"]))
        case["metadata"]["load_peak_MW"] = float(np.max(np.sum(case["D_P"], axis=1)))

    data_dir = BASE_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    settings_json, settings_csv = write_case_settings(case, data_dir)
    print(f"Case settings written: {settings_json}")
    print(pd.DataFrame([case["metadata"]]).T.to_string(header=False))

    if args.dry_run:
        return None

    from coalition_kernel_core import participant_labels, write_random_samples
    from dispatch_models import (
        optimize_price_taking_storage,
        solve_lmp_opf,
        solve_uc,
        solve_uc_with_storage,
    )
    from make_PTDF_es import PTDF

    ptdf = PTDF(case)
    initial_u = np.ones(int(case["TG_num"]))
    uc_no_es = solve_uc(
        args.case_tag + "_noES",
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
        ptdf["branch_max"],
        ptdf["PTDF"],
        ptdf["A_TG"],
        ptdf["A_RG"],
        ptdf["A_D"],
        case["TG_start_cost"].astype(float),
        case["TG_stop_cost"].astype(float),
        initial_u=initial_u,
        load_shed_penalty=float(case["load_shed_penalty"]),
        renewable_curtailment_penalty=float(case["renewable_curtailment_penalty"]),
        thermal_curtailment_penalty=float(case["thermal_curtailment_penalty"]),
    )

    lmp = solve_lmp_opf(
        args.case_tag + "_noES",
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
        ptdf["branch_max"],
        ptdf["PTDF"],
        ptdf["A_TG"],
        ptdf["A_RG"],
        ptdf["A_D"],
        load_shed_penalty=float(case["load_shed_penalty"]),
        renewable_curtailment_penalty=float(case["renewable_curtailment_penalty"]),
        thermal_curtailment_penalty=float(case["thermal_curtailment_penalty"]),
    )
    prices = (lmp["LMP"] @ ptdf["A_ES"]).T
    storage = optimize_price_taking_storage(
        args.case_tag,
        case["T"],
        prices,
        case["ES_ramp"].astype(float),
        case["ES_P"].astype(float),
        case["eff"].astype(float),
    )

    uc_with_es = solve_uc_with_storage(
        args.case_tag,
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
        ptdf["branch_max"],
        ptdf["PTDF"],
        ptdf["A_TG"],
        ptdf["A_RG"],
        ptdf["A_D"],
        ptdf["A_ES"],
        case["ES_ramp"].astype(float),
        case["ES_P"].astype(float),
        case["eff"].astype(float),
        storage["penalty_charge_matrix"],
        storage["bid_discharge_matrix"],
        case["TG_start_cost"].astype(float),
        case["TG_stop_cost"].astype(float),
        initial_u=initial_u,
        load_shed_penalty=float(case["load_shed_penalty"]),
        renewable_curtailment_penalty=float(case["renewable_curtailment_penalty"]),
        thermal_curtailment_penalty=float(case["thermal_curtailment_penalty"]),
    )

    p_charge = np.maximum(uc_with_es["s"], 0.0)
    p_discharge = -np.minimum(uc_with_es["s"], 0.0)
    p_discharge[p_discharge == -0.0] = 0.0
    split_case = split_storage_roles(case, uc_with_es, p_charge, p_discharge)

    case_path = data_dir / f"case_example_dict_{args.case_tag}.pkl"
    with case_path.open("wb") as f:
        pickle.dump(split_case, f)
    print(f"KernelSHAP case pickle written: {case_path}")

    summary = dispatch_summary(case, uc_no_es, uc_with_es)
    metadata = {
        "experiment": "ieee118_price_taking_scale_case",
        "case_tag": args.case_tag,
        "case_path": str(case_path),
        "case_settings_path": str(settings_csv),
        "n_agents_origin": int(split_case["TG_num"] + split_case["RG_num"] + split_case["D_num"]),
        "n_agents_merged": len(participant_labels(split_case)) - int(split_case["ES_num"]),
        "participant_labels_origin": participant_labels(split_case),
        "kernel_num": int(args.kernel_num),
        "samples_per_kernel": int(args.samples_per_kernel),
        "random_seed": int(args.seed),
        "case_builder_metadata": case["metadata"],
        "dispatch_summary": summary,
        "storage_split_note": split_case["storage_split_note"],
    }
    metadata_path = data_dir / f"metadata_{args.case_tag}.json"
    metadata_path.write_text(json.dumps(to_jsonable(metadata), indent=2))

    pd.DataFrame([summary]).to_excel(data_dir / f"prepared_{args.case_tag}_summary.xlsx", index=False)
    pd.DataFrame([summary]).to_csv(data_dir / f"prepared_{args.case_tag}_summary.csv", index=False)
    pd.DataFrame(uc_no_es["u"]).to_csv(data_dir / f"UC_noES_{args.case_tag}.csv", index=False)
    pd.DataFrame(uc_with_es["u"]).to_csv(data_dir / f"UC_{args.case_tag}.csv", index=False)
    pd.DataFrame(uc_with_es["PG"]).to_csv(data_dir / f"PG_{args.case_tag}.csv", index=False)
    pd.DataFrame(uc_with_es["APG"]).to_csv(data_dir / f"APG_{args.case_tag}.csv", index=False)
    pd.DataFrame(uc_with_es["RG"]).to_csv(data_dir / f"RG_{args.case_tag}.csv", index=False)
    pd.DataFrame(uc_with_es["LS"]).to_csv(data_dir / f"LS_{args.case_tag}.csv", index=False)
    pd.DataFrame(uc_with_es["e"]).to_csv(data_dir / f"SOC_{args.case_tag}.csv", index=False)
    pd.DataFrame(p_charge).to_csv(data_dir / f"charge_{args.case_tag}.csv", index=False)
    pd.DataFrame(p_discharge).to_csv(data_dir / f"discharge_{args.case_tag}.csv", index=False)

    if not args.skip_random_samples:
        random_dir = BASE_DIR / "random_S_set" / args.case_tag
        write_random_samples(random_dir, metadata["n_agents_origin"], args.kernel_num, args.samples_per_kernel, args.seed)
        print(f"KernelSHAP random samples written: {random_dir}")

    print(pd.DataFrame([summary]).T.to_string(header=False))
    return summary


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare the IEEE 118-bus price-taking ESS scale case.")
    parser.add_argument(
        "--case-tag",
        default="PT118_ADJ_coal45_gas20_res300_one_local_fixedthermal_4h",
    )
    parser.add_argument("--case118-path", default=str(DEFAULT_CASE118_PATH))
    parser.add_argument("--profile-path", default=str(DEFAULT_PROFILE_PATH))
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--day-of-interest", type=int, default=300)
    parser.add_argument("--load-scale", type=float, default=1.0)
    parser.add_argument("--renewable-buses", default="54,65,80,89")
    parser.add_argument("--renewable-capacity-reference-buses", default="10,65,80,89")
    parser.add_argument("--renewable-capacity-to-peak", type=float, default=3.0)
    parser.add_argument("--ess-buses", default="59,90,116,54")
    parser.add_argument("--ess-power-to-peak", type=float, default=0.15)
    parser.add_argument("--ess-duration-h", type=float, default=4.0)
    parser.add_argument("--branch-limit-mw", type=float, default=500.0)
    parser.add_argument(
        "--branch-limit-overrides",
        default="",
        help="Comma-separated endpoint-specific limits, e.g. 8-9:650,9-10:650",
    )
    parser.add_argument("--coal-capacity-scale", type=float, default=0.45)
    parser.add_argument("--gas-capacity-scale", type=float, default=0.20)
    parser.add_argument("--capacity-rounding-mw", type=float, default=10.0)
    parser.add_argument("--kernel-num", type=int, default=5000)
    parser.add_argument("--samples-per-kernel", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1126)
    parser.add_argument("--smoke-hours", type=int, default=24)
    parser.add_argument("--skip-random-samples", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    prepare_case(parse_args())
