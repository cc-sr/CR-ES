import argparse
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from coalition_kernel_core import merged_labels, participant_labels  # noqa: E402
from coalition_kernel_core import patch_numpy_pickle_compatibility  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Collect period-wise KernelSHAP results into Excel.")
    parser.add_argument("--case-tag", required=True)
    parser.add_argument("--expected-periods", type=int, default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    base_dir = os.path.abspath(os.path.dirname(__file__))
    case_path = os.path.join(base_dir, "data", f"case_example_dict_{args.case_tag}.pkl")
    metadata_path = os.path.join(base_dir, "data", f"metadata_{args.case_tag}.json")
    output_dir = os.path.join(base_dir, "kernel_data", args.case_tag)
    result_dir = os.path.join(base_dir, "kernel_SHAP_results")
    os.makedirs(result_dir, exist_ok=True)

    patch_numpy_pickle_compatibility()
    with open(case_path, "rb") as f:
        case = pickle.load(f)
    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    t_count = int(case["T"]) if args.expected_periods is None else int(args.expected_periods)
    origin_labels = participant_labels(case)
    merged = merged_labels(case)

    origin_rows = []
    merged_rows = []
    merged_path_rows = []
    efficiency_rows = []
    time_rows = []
    for t in range(t_count):
        origin_file = os.path.join(output_dir, f"shap_origin_{t}.npy")
        merged_file = os.path.join(output_dir, f"shap_merged_{t}.npy")
        shap_all_file = os.path.join(output_dir, f"shap_all_{t}.npy")
        sample_counts_file = os.path.join(output_dir, f"sample_counts_{t}.npy")
        full_file = os.path.join(output_dir, f"fai_all_{t}.npy")
        time_file = os.path.join(output_dir, f"total_time_{t}.npy")
        if not os.path.exists(origin_file):
            raise FileNotFoundError(f"Missing period result: {origin_file}")
        origin_phi = np.load(origin_file)
        merged_phi = np.load(merged_file)
        full_value = float(np.load(full_file))
        total_time = float(np.load(time_file))
        if os.path.exists(shap_all_file) and os.path.exists(sample_counts_file):
            merged_path = np.load(shap_all_file)
            sample_counts = np.load(sample_counts_file)
            for sample_count, merged_checkpoint in zip(sample_counts, merged_path):
                merged_path_rows.append([t, int(sample_count)] + merged_checkpoint.tolist())
        origin_rows.append([t] + origin_phi.tolist())
        merged_rows.append([t] + merged_phi.tolist())
        abs_gap = float(abs(origin_phi.sum() - full_value))
        rel_gap = abs_gap / full_value if abs(full_value) > 1e-12 else 0.0
        efficiency_rows.append([t, full_value, float(origin_phi.sum()), abs_gap, rel_gap])
        time_rows.append([t, total_time])

    df_origin = pd.DataFrame(origin_rows, columns=["t"] + origin_labels)
    df_merged = pd.DataFrame(merged_rows, columns=["t"] + merged)
    df_merged_path = pd.DataFrame(merged_path_rows, columns=["t", "sample_count"] + merged)
    if df_merged_path.empty:
        df_shap_all = pd.DataFrame(columns=merged)
    else:
        df_shap_all = (
            df_merged_path.groupby("sample_count", sort=True)[merged]
            .sum()
            .reset_index(drop=True)
        )
    df_eff = pd.DataFrame(
        efficiency_rows,
        columns=["t", "full_coalition_emissions", "sum_allocations", "absolute_gap", "relative_gap"],
    )
    df_time = pd.DataFrame(time_rows, columns=["t", "TotalTime_t"])

    origin_total = df_origin[origin_labels].sum(axis=0)
    merged_total = df_merged[merged].sum(axis=0)
    df_origin_total = pd.DataFrame([origin_total], columns=origin_labels)
    df_merged_total = pd.DataFrame([merged_total], columns=merged)
    df_total_time_all = pd.DataFrame([{"TotalTime_all": float(df_time["TotalTime_t"].sum())}])

    es_rows = []
    tg_num = int(case["TG_num"])
    real_rg_num = int(case["real_RG_num"])
    rg_num = int(case["RG_num"])
    real_d_num = int(case["real_D_num"])
    es_num = int(case["ES_num"])
    dis_start = tg_num + real_rg_num
    ch_start = tg_num + rg_num + real_d_num
    for es_idx in range(es_num):
        dis_label = origin_labels[dis_start + es_idx]
        ch_label = origin_labels[ch_start + es_idx]
        discharge_credit = float(origin_total[dis_label])
        charging_responsibility = float(origin_total[ch_label])
        net = charging_responsibility + discharge_credit
        throughput = float(np.sum(case["p_charge"][:, es_idx] + case["p_discharge"][:, es_idx]))
        es_rows.append(
            {
                "ESS": f"ES{es_idx + 1}",
                "charging_responsibility": charging_responsibility,
                "discharging_credit": discharge_credit,
                "net_allocation": net,
                "throughput_MWh": throughput,
                "net_per_throughput": net / throughput if throughput > 1e-12 else np.nan,
            }
        )
    df_es = pd.DataFrame(es_rows)

    output_path = os.path.join(result_dir, f"kernelSHAP_{args.case_tag}.xlsx")
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame([metadata["dispatch_summary"]]).to_excel(writer, sheet_name="dispatch_summary", index=False)
        df_merged.to_excel(writer, sheet_name="SHAP_t", index=False)
        df_origin.to_excel(writer, sheet_name="SHAP_t_origin", index=False)
        df_time.to_excel(writer, sheet_name="TotalTime_t", index=False)
        df_shap_all.to_excel(writer, sheet_name="SHAP_all", index=False)
        df_total_time_all.to_excel(writer, sheet_name="TotalTime_all", index=False)
        df_merged_total.to_excel(writer, sheet_name="SHAP_total", index=False)
        df_origin_total.to_excel(writer, sheet_name="SHAP_total_origin", index=False)
        df_es.to_excel(writer, sheet_name="ESS_decomposition", index=False)
        df_eff.to_excel(writer, sheet_name="efficiency_check", index=False)

    print("Saved:", output_path)
    print(df_merged_total.to_string(index=False))
    print(df_eff[["absolute_gap", "relative_gap"]].describe().to_string())


if __name__ == "__main__":
    main()
