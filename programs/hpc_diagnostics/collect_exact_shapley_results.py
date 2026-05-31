import argparse
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

WORKFLOW_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(WORKFLOW_DIR)

from coalition_kernel_core import merged_labels, participant_labels, patch_numpy_pickle_compatibility  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Collect IEEE14 exact Shapley results.")
    parser.add_argument("--case-tag", required=True)
    parser.add_argument("--expected-periods", type=int, default=24)
    return parser.parse_args()


def compute_error_metrics(exact, approx):
    exact = np.asarray(exact, dtype=float)
    approx = np.asarray(approx, dtype=float)
    diff = approx - exact
    red = np.linalg.norm(diff) / (np.linalg.norm(exact) + 1e-12)
    rmse = float(np.sqrt(np.mean(diff ** 2)))
    nrmse = rmse / (np.mean(np.abs(exact)) + 1e-12) * 100
    cs = float(np.dot(approx, exact) / ((np.linalg.norm(approx) + 1e-12) * (np.linalg.norm(exact) + 1e-12)))
    mae = float(np.mean(np.abs(diff)))
    return {
        "RED": float(red),
        "RMSE": rmse,
        "NRMSE_pct": float(nrmse),
        "CS": cs,
        "MAE_tCO2": mae,
    }


def main():
    args = parse_args()
    case_path = os.path.join(WORKFLOW_DIR, "data", f"case_example_dict_{args.case_tag}.pkl")
    metadata_path = os.path.join(WORKFLOW_DIR, "data", f"metadata_{args.case_tag}.json")
    exact_dir = os.path.join(WORKFLOW_DIR, "exact_shapley_data", args.case_tag)
    result_dir = os.path.join(WORKFLOW_DIR, "exact_shapley_results")
    os.makedirs(result_dir, exist_ok=True)

    patch_numpy_pickle_compatibility()
    with open(case_path, "rb") as f:
        case = pickle.load(f)
    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    origin_labels = participant_labels(case)
    merged = merged_labels(case)
    origin_rows = []
    merged_rows = []
    efficiency_rows = []
    time_rows = []
    for t in range(int(args.expected_periods)):
        origin_phi = np.load(os.path.join(exact_dir, f"exact_origin_{t}.npy"))
        merged_phi = np.load(os.path.join(exact_dir, f"exact_merged_{t}.npy"))
        full_value = float(np.load(os.path.join(exact_dir, f"exact_full_value_{t}.npy")))
        empty_value = float(np.load(os.path.join(exact_dir, f"exact_empty_value_{t}.npy")))
        total_time = float(np.load(os.path.join(exact_dir, f"exact_total_time_{t}.npy")))
        origin_rows.append([t] + origin_phi.tolist())
        merged_rows.append([t] + merged_phi.tolist())
        target = full_value - empty_value
        abs_gap = float(abs(origin_phi.sum() - target))
        rel_gap = abs_gap / target if abs(target) > 1e-12 else 0.0
        efficiency_rows.append([t, full_value, empty_value, target, float(origin_phi.sum()), abs_gap, rel_gap])
        time_rows.append([t, total_time])

    df_origin = pd.DataFrame(origin_rows, columns=["t"] + origin_labels)
    df_merged = pd.DataFrame(merged_rows, columns=["t"] + merged)
    df_eff = pd.DataFrame(
        efficiency_rows,
        columns=[
            "t",
            "full_coalition_emissions",
            "empty_coalition_emissions",
            "target_value",
            "sum_allocations",
            "absolute_gap",
            "relative_gap",
        ],
    )
    df_time = pd.DataFrame(time_rows, columns=["t", "ExactTime_t"])
    df_origin_total = pd.DataFrame([df_origin[origin_labels].sum(axis=0)], columns=origin_labels)
    df_merged_total = pd.DataFrame([df_merged[merged].sum(axis=0)], columns=merged)
    df_total_time_all = pd.DataFrame([{"ExactTime_all": float(df_time["ExactTime_t"].sum())}])

    comparison_rows = []
    kernel_path = os.path.join(WORKFLOW_DIR, "kernel_SHAP_results", f"kernelSHAP_{args.case_tag}.xlsx")
    if os.path.exists(kernel_path):
        kernel_total = pd.read_excel(kernel_path, sheet_name="SHAP_total").iloc[0][merged].astype(float).to_numpy()
        exact_total = df_merged_total.iloc[0][merged].astype(float).to_numpy()
        comparison_rows.append({"scope": "24h_merged_total", **compute_error_metrics(exact_total, kernel_total)})
    df_comparison = pd.DataFrame(comparison_rows)

    output_path = os.path.join(result_dir, f"exactShapley_{args.case_tag}.xlsx")
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame([metadata["dispatch_summary"]]).to_excel(writer, sheet_name="dispatch_summary", index=False)
        df_merged.to_excel(writer, sheet_name="Shapley_t", index=False)
        df_origin.to_excel(writer, sheet_name="Shapley_t_origin", index=False)
        df_time.to_excel(writer, sheet_name="ExactTime_t", index=False)
        df_total_time_all.to_excel(writer, sheet_name="ExactTime_all", index=False)
        df_merged_total.to_excel(writer, sheet_name="Shapley_total", index=False)
        df_origin_total.to_excel(writer, sheet_name="Shapley_total_origin", index=False)
        df_eff.to_excel(writer, sheet_name="efficiency_check", index=False)
        if not df_comparison.empty:
            df_comparison.to_excel(writer, sheet_name="KernelSHAP_error", index=False)

    print("Saved:", output_path)
    print(df_merged_total.to_string(index=False))
    if not df_comparison.empty:
        print(df_comparison.to_string(index=False))
    print(df_eff[["absolute_gap", "relative_gap"]].describe().to_string())


if __name__ == "__main__":
    main()
