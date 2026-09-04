import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parents[1]
DEFAULT_CASE118_PATH = BASE_DIR / "case118.m"
DEFAULT_PROFILE_PATH = REPO_ROOT / "data" / "input_profiles" / "ieee118_profile_data.xlsx"


def _extract_matpower_matrix(text, name):
    match = re.search(rf"mpc\.{name}\s*=\s*\[(.*?)\];", text, flags=re.S)
    if not match:
        raise ValueError(f"Cannot find mpc.{name} matrix in MATPOWER case file.")
    rows = []
    for raw_line in match.group(1).splitlines():
        line = raw_line.split("%", 1)[0].replace(";", " ").strip()
        if not line:
            continue
        rows.append([float(x) for x in line.split()])
    return np.asarray(rows, dtype=float)


def read_matpower_case118(case_path=DEFAULT_CASE118_PATH):
    case_path = Path(case_path)
    text = case_path.read_text()
    return {
        "bus": _extract_matpower_matrix(text, "bus"),
        "gen": _extract_matpower_matrix(text, "gen"),
        "branch": _extract_matpower_matrix(text, "branch"),
    }


def _as_bus_list(value):
    if isinstance(value, (list, tuple, np.ndarray)):
        return [int(v) for v in value]
    return [int(v.strip()) for v in str(value).split(",") if v.strip()]


def _parse_branch_limit_overrides(value):
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return {
            tuple(sorted((int(k[0]), int(k[1])))): float(v)
            for k, v in value.items()
        }
    overrides = {}
    for item in str(value).split(","):
        endpoints, limit = item.split(":", 1)
        from_bus, to_bus = endpoints.split("-", 1)
        overrides[tuple(sorted((int(from_bus), int(to_bus))))] = float(limit)
    return overrides


def _select_rows_by_bus(matrix, bus_col, buses):
    buses = set(int(b) for b in buses)
    return np.asarray([row for row in matrix if int(row[bus_col]) in buses], dtype=float)


def _round_to_step(values, step=10.0, minimum=None):
    rounded = np.round(np.asarray(values, dtype=float) / float(step)) * float(step)
    if minimum is not None:
        rounded = np.maximum(rounded, float(minimum))
    return rounded


def _make_daily_profiles(profile_path, day_of_interest, hours):
    df = pd.read_excel(profile_path)
    start = (int(day_of_interest) - 1) * 24
    end = start + int(hours)
    if end > len(df):
        raise ValueError(
            f"Profile file has {len(df)} rows; requested rows [{start}, {end})."
        )
    load_profiles = np.asarray(df.iloc[start:end, 0:8], dtype=float)
    renewable_profiles = np.asarray(df.iloc[start:end, -2:], dtype=float)
    return np.clip(load_profiles, 0.0, None), np.clip(renewable_profiles, 0.0, None)


def build_ieee118_price_taking_case(
    case_tag="PT118_ADJ_coal45_gas20_res300_one_local_fixedthermal_4h",
    case118_path=DEFAULT_CASE118_PATH,
    profile_path=DEFAULT_PROFILE_PATH,
    days=1,
    day_of_interest=300,
    load_scale=1.0,
    renewable_buses=(54, 65, 80, 89),
    renewable_capacity_reference_buses=(10, 65, 80, 89),
    renewable_capacity_to_peak=3.0,
    ess_buses=(59, 90, 116, 54),
    ess_power_to_peak=0.15,
    ess_duration_h=4.0,
    branch_limit_mw=500.0,
    branch_limit_overrides=None,
    coal_capacity_scale=0.45,
    gas_capacity_scale=0.20,
    capacity_rounding_mw=10.0,
    random_seed=1126,
):
    """Construct an IEEE 118-bus price-taking ESS case using the paper's data schema.

    The MATPOWER file provides topology, load buses, and generator buses. The
    time-series profiles and ESS/RG/TG modeling choices follow the same schema
    used by the IEEE 14-bus and IEEE 30-bus manuscript cases.
    """

    raw = read_matpower_case118(case118_path)
    bus = raw["bus"]
    gen = raw["gen"]
    branch_raw = raw["branch"]

    hours = int(days) * 24
    load_profile_pool, renewable_profile_pool = _make_daily_profiles(
        profile_path, day_of_interest, hours
    )

    bus_num = int(np.max(bus[:, 0]))
    online_gen = gen[gen[:, 7] > 0.5]
    renewable_buses = _as_bus_list(renewable_buses)
    renewable_capacity_reference_buses = _as_bus_list(renewable_capacity_reference_buses)
    ess_buses = _as_bus_list(ess_buses)

    if len(set(renewable_buses)) != len(renewable_buses):
        raise ValueError("renewable_buses must contain unique bus numbers.")
    if any(bus_id < 1 or bus_id > bus_num for bus_id in renewable_buses):
        raise ValueError(f"renewable_buses must be within 1 and {bus_num}.")

    renewable_rows = _select_rows_by_bus(online_gen, 0, renewable_capacity_reference_buses)
    if len(renewable_rows) != len(renewable_capacity_reference_buses):
        found = set(int(row[0]) for row in renewable_rows)
        missing = [b for b in renewable_capacity_reference_buses if b not in found]
        raise ValueError(f"Renewable buses without online generator rows: {missing}")

    thermal_rows = np.asarray(
        [
            row
            for row in online_gen
            if int(row[0]) not in set(renewable_capacity_reference_buses)
        ],
        dtype=float,
    )
    if len(thermal_rows) == 0:
        raise ValueError("No thermal generators remain after selecting renewable buses.")

    load_rows = bus[bus[:, 2] > 1e-9]
    d_bl = load_rows[:, 0].astype(int)
    d_p_base = load_rows[:, 2].astype(float) * float(load_scale)
    rng = np.random.default_rng(int(random_seed))
    load_cols = rng.integers(0, load_profile_pool.shape[1], size=len(d_bl))
    d_p = np.column_stack(
        [load_profile_pool[:, col] * d_p_base[i] for i, col in enumerate(load_cols)]
    )
    load_peak = float(np.max(np.sum(d_p, axis=1)))

    rg_original_pmax = renewable_rows[:, 8].astype(float)
    rg_total_capacity = float(renewable_capacity_to_peak) * load_peak
    rg_p = rg_total_capacity * rg_original_pmax / np.sum(rg_original_pmax)
    if capacity_rounding_mw > 0:
        rg_p = _round_to_step(rg_p, capacity_rounding_mw, minimum=capacity_rounding_mw)
    rg_profile_cols = np.arange(len(rg_p)) % renewable_profile_pool.shape[1]
    rg_cap = renewable_profile_pool[:, rg_profile_cols]

    tg_pmax_original = thermal_rows[:, 8].astype(float)
    gas_mask = tg_pmax_original <= 120.0
    tg_scale = np.where(gas_mask, float(gas_capacity_scale), float(coal_capacity_scale))
    tg_pmax = tg_pmax_original * tg_scale
    if capacity_rounding_mw > 0:
        tg_pmax = _round_to_step(tg_pmax, capacity_rounding_mw, minimum=capacity_rounding_mw)
    tg_offer = np.where(gas_mask, 850.0, 400.0)
    tg_carbon = np.where(gas_mask, 0.44, 1.044)
    tg_min = np.where(gas_mask, 0.25 * tg_pmax, 0.35 * tg_pmax)
    tg_ramp = np.where(gas_mask, 6.0 * tg_pmax, 0.60 * tg_pmax)
    tg_start_cost = np.where(gas_mask, 150.0 * tg_pmax, 800.0 * tg_pmax)
    tg_stop_cost = np.where(gas_mask, 30.0 * tg_pmax, 160.0 * tg_pmax)
    t_on = np.where(gas_mask, 1, 4).astype(int)
    t_off = np.where(gas_mask, 1, 6).astype(int)

    branch_active = branch_raw[branch_raw[:, 10] > 0.5]
    if np.any(np.abs(branch_active[:, 3]) < 1e-12):
        bad = branch_active[np.abs(branch_active[:, 3]) < 1e-12][:, :2].astype(int)
        raise ValueError(f"Branches with zero reactance cannot be used in DC PTDF: {bad}")
    branch = np.column_stack(
        [
            branch_active[:, 0],
            branch_active[:, 1],
            branch_active[:, 3],
            np.full(len(branch_active), float(branch_limit_mw)),
        ]
    )
    branch_limit_overrides = _parse_branch_limit_overrides(branch_limit_overrides)
    for row in branch:
        key = tuple(sorted((int(row[0]), int(row[1]))))
        if key in branch_limit_overrides:
            row[3] = branch_limit_overrides[key]

    es_num = len(ess_buses)
    es_total_power = float(ess_power_to_peak) * load_peak
    es_ramp = np.full(es_num, es_total_power / es_num)
    if capacity_rounding_mw > 0:
        es_ramp = _round_to_step(es_ramp, capacity_rounding_mw, minimum=capacity_rounding_mw)
    es_p = es_ramp * float(ess_duration_h)

    case = {
        "case_tag": str(case_tag),
        "T": int(hours),
        "TG_num": int(len(thermal_rows)),
        "RG_num": int(len(rg_p)),
        "D_num": int(len(d_bl)),
        "ES_num": int(es_num),
        "bus_num": int(bus_num),
        "branch_num": int(len(branch)),
        "TG_bl": thermal_rows[:, 0].astype(int),
        "TG_offer": tg_offer.astype(float),
        "TG_carbon": tg_carbon.astype(float),
        "TG_maxG": tg_pmax.astype(float),
        "TG_minG": tg_min.astype(float),
        "TG_ramp": tg_ramp.astype(float),
        "TG_start_cost": tg_start_cost.astype(float),
        "TG_stop_cost": tg_stop_cost.astype(float),
        "T_on": t_on.astype(int),
        "T_off": t_off.astype(int),
        "RG_bl": np.asarray(renewable_buses, dtype=int),
        "RG_offer": np.zeros(len(rg_p), dtype=float),
        "RG_P": rg_p.astype(float),
        "RG_ramp": np.maximum(rg_p / 0.6, 1e-6).astype(float),
        "RG_cap": rg_cap.astype(float),
        "D_bl": d_bl.astype(int),
        "D_P": d_p.astype(float),
        "branch": branch.astype(float),
        "branch_limit_overrides": {
            f"{from_bus}-{to_bus}": float(limit)
            for (from_bus, to_bus), limit in branch_limit_overrides.items()
        },
        "renewable_capacity_reference_buses": np.asarray(
            renewable_capacity_reference_buses, dtype=int
        ),
        "ES_bl": np.asarray(ess_buses, dtype=int),
        "ES_ramp": es_ramp.astype(float),
        "ES_P": es_p.astype(float),
        "ES_offer": np.zeros(es_num, dtype=float),
        "eff": np.full(es_num, 0.90, dtype=float),
        "load_shed_penalty": 5000.0,
        "renewable_curtailment_penalty": 100.0,
        "thermal_curtailment_penalty": 200.0,
        "coal_capacity_scale": float(coal_capacity_scale),
        "gas_capacity_scale": float(gas_capacity_scale),
        "capacity_rounding_mw": float(capacity_rounding_mw),
    }

    case["metadata"] = make_case_metadata(case, raw, gas_mask, load_cols)
    return case


def make_case_metadata(case, raw, gas_mask, load_cols):
    d_p = case["D_P"]
    load_energy = float(np.sum(d_p))
    load_peak = float(np.max(np.sum(d_p, axis=1)))
    return {
        "source_case": "MATPOWER case118",
        "hours": int(case["T"]),
        "bus_num": int(case["bus_num"]),
        "branch_num": int(case["branch_num"]),
        "thermal_generator_count": int(case["TG_num"]),
        "renewable_generator_count": int(case["RG_num"]),
        "load_count": int(case["D_num"]),
        "ess_count": int(case["ES_num"]),
        "origin_agent_count_before_ess_recombination": int(
            case["TG_num"] + case["RG_num"] + case["D_num"] + 2 * case["ES_num"]
        ),
        "merged_agent_count_after_ess_recombination": int(
            case["TG_num"] + case["RG_num"] + case["D_num"] + case["ES_num"]
        ),
        "load_energy_MWh": load_energy,
        "load_peak_MW": load_peak,
        "standard_case_total_Pd_MW": float(np.sum(raw["bus"][:, 2])),
        "thermal_capacity_MW": float(np.sum(case["TG_maxG"])),
        "renewable_capacity_MW": float(np.sum(case["RG_P"])),
        "ess_power_MW": float(np.sum(case["ES_ramp"])),
        "ess_energy_MWh": float(np.sum(case["ES_P"])),
        "renewable_capacity_to_peak_load_pct": float(100.0 * np.sum(case["RG_P"]) / load_peak),
        "renewable_capacity_reference_buses": [
            int(x) for x in case["renewable_capacity_reference_buses"]
        ],
        "ess_power_to_peak_load_pct": float(100.0 * np.sum(case["ES_ramp"]) / load_peak),
        "ess_duration_h": float(np.mean(case["ES_P"] / case["ES_ramp"])),
        "thermal_type_rule": "Pmax <= 120 MW is modeled as gas; larger units are modeled as coal.",
        "thermal_gas_count": int(np.sum(gas_mask)),
        "thermal_coal_count": int(np.sum(~gas_mask)),
        "coal_capacity_scale": float(case["coal_capacity_scale"]),
        "gas_capacity_scale": float(case["gas_capacity_scale"]),
        "capacity_rounding_MW": float(case["capacity_rounding_mw"]),
        "branch_limit_MW": float(case["branch"][0, 3]) if len(case["branch"]) else 0.0,
        "branch_limit_overrides": dict(case.get("branch_limit_overrides", {})),
        "load_profile_columns": [int(x) for x in load_cols],
        "renewable_buses": [int(x) for x in case["RG_bl"]],
        "ess_buses": [int(x) for x in case["ES_bl"]],
        "notes": [
            "Topology, load buses, and generator buses are parsed from MATPOWER case118.",
            "Time-series profiles are read from the processed load and renewable workbook in data/input_profiles.",
            "RES capacity and ESS power are set from approximate peak-load percentage targets and rounded to the selected MW step.",
            "Thermal generator capacities can be scaled by fuel type and rounded to the selected MW step.",
            "MATPOWER rateA=0 is treated as unspecified; this builder assigns an explicit configurable branch limit.",
        ],
    }


def to_jsonable(value):
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def write_case_settings(case, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"case_settings_{case['case_tag']}.json"
    json_path.write_text(json.dumps(to_jsonable(case["metadata"]), indent=2))

    summary_path = output_dir / f"case_settings_{case['case_tag']}.csv"
    pd.DataFrame([case["metadata"]]).to_csv(summary_path, index=False)
    return json_path, summary_path
