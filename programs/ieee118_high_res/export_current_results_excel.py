"""Export the completed IEEE 118-bus results to a single Excel workbook.

The script reads the saved Stage-1 workbooks and the period-wise KernelSHAP
checkpoints already produced on HPC.  It does not rerun UC, OPF, or sampling.
"""

import argparse
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(BASE_DIR)

from coalition_kernel_core import merged_labels, participant_labels  # noqa: E402
from coalition_kernel_core import patch_numpy_pickle_compatibility  # noqa: E402


DEFAULT_CASE_TAG = "PT118_ADJ_coal45_gas20_res300_one_local_fixedthermal_4h"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export completed IEEE 118-bus Stage-1 and KernelSHAP results."
    )
    parser.add_argument("--case-tag", default=DEFAULT_CASE_TAG)
    parser.add_argument("--expected-periods", type=int, default=24)
    parser.add_argument("--output-name", default=None)
    return parser.parse_args()


def load_period_results(kernel_dir, t_count, origin_labels, merged):
    origin_rows = []
    merged_rows = []
    checkpoint_rows = []
    efficiency_rows = []
    runtime_rows = []
    checkpoint_counts_by_period = []

    for t in range(t_count):
        origin_file = os.path.join(kernel_dir, f"shap_origin_{t}.npy")
        merged_file = os.path.join(kernel_dir, f"shap_merged_{t}.npy")
        full_file = os.path.join(kernel_dir, f"fai_all_{t}.npy")
        time_file = os.path.join(kernel_dir, f"total_time_{t}.npy")
        checkpoint_file = os.path.join(kernel_dir, f"shap_all_{t}.npy")
        count_file = os.path.join(kernel_dir, f"sample_counts_{t}.npy")

        required = [origin_file, merged_file, full_file, time_file]
        missing = [path for path in required if not os.path.exists(path)]
        if missing:
            raise FileNotFoundError("Missing saved result files: " + ", ".join(missing))

        origin_phi = np.asarray(np.load(origin_file), dtype=float)
        merged_phi = np.asarray(np.load(merged_file), dtype=float)
        full_value = float(np.load(full_file))
        total_time = float(np.load(time_file))

        origin_rows.append([t] + origin_phi.tolist())
        merged_rows.append([t] + merged_phi.tolist())
        efficiency_rows.append(
            {
                "period": t,
                "full_coalition_emissions": full_value,
                "sum_allocations": float(origin_phi.sum()),
                "absolute_gap": float(abs(origin_phi.sum() - full_value)),
                "relative_gap": float(abs(origin_phi.sum() - full_value) / full_value)
                if abs(full_value) > 1e-12
                else 0.0,
            }
        )
        runtime_rows.append({"period": t, "KernelSHAP_time_s": total_time})

        if os.path.exists(checkpoint_file) and os.path.exists(count_file):
            checkpoint_phi = np.asarray(np.load(checkpoint_file), dtype=float)
            sample_counts = np.asarray(np.load(count_file), dtype=int).reshape(-1)
            if checkpoint_phi.ndim != 2:
                raise ValueError(f"Expected a 2-D checkpoint array: {checkpoint_file}")
            if checkpoint_phi.shape[0] != len(sample_counts):
                raise ValueError(
                    f"Checkpoint/count mismatch for period {t}: "
                    f"{checkpoint_phi.shape[0]} vs {len(sample_counts)}"
                )
            checkpoint_counts_by_period.append(sample_counts)
            for sample_count, phi in zip(sample_counts, checkpoint_phi):
                checkpoint_rows.append([t, int(sample_count)] + phi.tolist())

    origin = pd.DataFrame(origin_rows, columns=["period"] + origin_labels)
    merged_df = pd.DataFrame(merged_rows, columns=["period"] + merged)
    checkpoint_df = pd.DataFrame(
        checkpoint_rows, columns=["period", "sample_count"] + merged
    )
    efficiency = pd.DataFrame(efficiency_rows)
    runtime = pd.DataFrame(runtime_rows)

    if checkpoint_counts_by_period:
        reference = checkpoint_counts_by_period[0]
        for counts in checkpoint_counts_by_period[1:]:
            if not np.array_equal(counts, reference):
                raise ValueError("Sample-count checkpoints differ between periods.")

    return origin, merged_df, checkpoint_df, efficiency, runtime


def add_stage1_workbooks(writer, result_dir):
    """Copy every existing Stage-1 workbook into uniquely named sheets."""
    if not os.path.isdir(result_dir):
        return

    for workbook_path in sorted(
        os.path.join(result_dir, name)
        for name in os.listdir(result_dir)
        if name.lower().endswith((".xlsx", ".xls"))
    ):
        stem = os.path.splitext(os.path.basename(workbook_path))[0]
        excel_file = pd.ExcelFile(workbook_path)
        for source_sheet in excel_file.sheet_names:
            frame = pd.read_excel(workbook_path, sheet_name=source_sheet)
            base_sheet_name = f"{stem}_{source_sheet}"
            sheet_name = base_sheet_name[:31]
            frame.to_excel(writer, sheet_name=sheet_name, index=False)


def build_ess_decomposition(case, origin_total, origin_labels):
    tg_num = int(case["TG_num"])
    real_rg_num = int(case["real_RG_num"])
    rg_num = int(case["RG_num"])
    real_d_num = int(case["real_D_num"])
    es_num = int(case["ES_num"])
    dis_start = tg_num + real_rg_num
    ch_start = tg_num + rg_num + real_d_num

    rows = []
    for es_idx in range(es_num):
        discharge_label = origin_labels[dis_start + es_idx]
        charging_label = origin_labels[ch_start + es_idx]
        discharge_credit = float(origin_total[discharge_label])
        charging_responsibility = float(origin_total[charging_label])
        net = charging_responsibility + discharge_credit
        throughput = float(
            np.sum(case["p_charge"][:, es_idx] + case["p_discharge"][:, es_idx])
        )
        rows.append(
            {
                "ESS": f"ES{es_idx + 1}",
                "charging_responsibility": charging_responsibility,
                "discharging_credit": discharge_credit,
                "net_allocation": net,
                "throughput_MWh": throughput,
                "net_per_throughput": net / throughput
                if throughput > 1e-12
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def main():
    args = parse_args()
    case_tag = args.case_tag
    data_dir = os.path.join(BASE_DIR, "data")
    kernel_dir = os.path.join(BASE_DIR, "kernel_data", case_tag)
    result_dir = os.path.join(BASE_DIR, "results")
    export_dir = os.path.join(result_dir, "exported")
    os.makedirs(export_dir, exist_ok=True)

    case_path = os.path.join(data_dir, f"case_example_dict_{case_tag}.pkl")
    metadata_path = os.path.join(data_dir, f"metadata_{case_tag}.json")
    patch_numpy_pickle_compatibility()
    with open(case_path, "rb") as file:
        case = pickle.load(file)
    with open(metadata_path, "r") as file:
        metadata = json.load(file)

    origin_labels = participant_labels(case)
    merged = merged_labels(case)
    origin, merged_df, checkpoints, efficiency, runtime = load_period_results(
        kernel_dir, args.expected_periods, origin_labels, merged
    )

    origin_total = origin[origin_labels].sum(axis=0)
    merged_total = merged_df[merged].sum(axis=0)
    total_time = float(runtime["KernelSHAP_time_s"].sum())

    if checkpoints.empty:
        checkpoint_total = pd.DataFrame(columns=["sample_count"] + merged)
    else:
        checkpoint_total = (
            checkpoints.groupby("sample_count", sort=True)[merged]
            .sum()
            .reset_index()
        )

    efficiency = pd.concat(
        [
            efficiency,
            pd.DataFrame(
                [
                    {
                        "period": "all",
                        "full_coalition_emissions": efficiency[
                            "full_coalition_emissions"
                        ].sum(),
                        "sum_allocations": efficiency["sum_allocations"].sum(),
                        "absolute_gap": abs(
                            efficiency["sum_allocations"].sum()
                            - efficiency["full_coalition_emissions"].sum()
                        ),
                        "relative_gap": abs(
                            efficiency["sum_allocations"].sum()
                            - efficiency["full_coalition_emissions"].sum()
                        )
                        / efficiency["full_coalition_emissions"].sum(),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    output_name = args.output_name or f"IEEE118_results_{case_tag}.xlsx"
    output_path = os.path.join(export_dir, output_name)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        add_stage1_workbooks(writer, result_dir)
        pd.DataFrame([metadata.get("dispatch_summary", {})]).to_excel(
            writer, sheet_name="dispatch_summary", index=False
        )
        origin.to_excel(writer, sheet_name="SHAP_t_origin", index=False)
        merged_df.to_excel(writer, sheet_name="SHAP_t", index=False)
        pd.DataFrame([origin_total], columns=origin_labels).to_excel(
            writer, sheet_name="SHAP_total_origin", index=False
        )
        pd.DataFrame([merged_total], columns=merged).to_excel(
            writer, sheet_name="SHAP_total", index=False
        )
        checkpoints.to_excel(writer, sheet_name="SHAP_checkpoints_t", index=False)
        checkpoint_total.to_excel(writer, sheet_name="SHAP_checkpoints_total", index=False)
        build_ess_decomposition(case, origin_total, origin_labels).to_excel(
            writer, sheet_name="ESS_decomposition", index=False
        )
        efficiency.to_excel(writer, sheet_name="efficiency_check", index=False)
        runtime.to_excel(writer, sheet_name="KernelSHAP_runtime", index=False)
        pd.DataFrame(
            [
                {
                    "periods": args.expected_periods,
                    "participants_before_ESS_recombination": len(origin_labels),
                    "participants_after_ESS_recombination": len(merged),
                    "checkpoint_count_per_period": int(
                        checkpoints["sample_count"].nunique()
                    )
                    if not checkpoints.empty
                    else 0,
                    "final_sample_count_per_period": int(
                        checkpoints["sample_count"].max()
                    )
                    if not checkpoints.empty
                    else 0,
                    "total_kernelshap_time_s": total_time,
                }
            ]
        ).to_excel(writer, sheet_name="export_summary", index=False)

    print(f"Saved: {output_path}")
    print(f"Final samples per period: {checkpoints['sample_count'].max() if not checkpoints.empty else 0}")
    print(f"Total KernelSHAP time (s): {total_time:.3f}")
    print(efficiency.tail(1).to_string(index=False))


if __name__ == "__main__":
    main()
