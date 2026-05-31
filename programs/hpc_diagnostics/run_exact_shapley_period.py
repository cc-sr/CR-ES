import argparse
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

WORKFLOW_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(WORKFLOW_DIR)

from coalition_kernel_core import coalition_carbon_value, load_case, make_ptdf, merge_ess_roles  # noqa: E402

_CTX = None


def _init_worker(case_path, period):
    global _CTX
    case = load_case(case_path)
    _CTX = {
        "case": case,
        "ptdf_data": make_ptdf(case),
        "period": int(period),
        "n_agents": int(case["TG_num"] + case["RG_num"] + case["D_num"]),
    }


def _mask_to_coalition(mask, n_agents):
    bits = ((np.uint64(mask) >> np.arange(n_agents, dtype=np.uint64)) & np.uint64(1)).astype(float)
    return bits


def _evaluate_chunk(masks):
    case = _CTX["case"]
    ptdf_data = _CTX["ptdf_data"]
    period = _CTX["period"]
    n_agents = _CTX["n_agents"]
    out = np.empty(len(masks), dtype=float)
    for idx, mask in enumerate(masks):
        coalition = _mask_to_coalition(mask, n_agents)
        out[idx] = coalition_carbon_value(case, ptdf_data, period, coalition)
    return masks, out


def _bit_counts(total_masks):
    masks = np.arange(total_masks, dtype=np.uint64)
    byte_view = masks.view(np.uint8).reshape(total_masks, masks.itemsize)
    return np.unpackbits(byte_view, axis=1).sum(axis=1).astype(np.int16)


def exact_shapley_from_values(values, n_agents):
    total_masks = 1 << n_agents
    masks = np.arange(total_masks, dtype=np.uint64)
    counts = _bit_counts(total_masks)
    weights = np.zeros(n_agents, dtype=float)
    for k in range(n_agents):
        weights[k] = math.factorial(k) * math.factorial(n_agents - k - 1) / math.factorial(n_agents)

    phi = np.zeros(n_agents, dtype=float)
    for i in range(n_agents):
        bit = np.uint64(1 << i)
        without = (masks & bit) == 0
        base_masks = masks[without]
        with_masks = base_masks | bit
        phi[i] = np.sum(
            weights[counts[without]]
            * (values[with_masks.astype(np.intp)] - values[base_masks.astype(np.intp)])
        )
    return phi


def parse_args():
    parser = argparse.ArgumentParser(description="Run exact Shapley for one IEEE14 period.")
    parser.add_argument("--case-tag", required=True)
    parser.add_argument("--period", type=int, default=None)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--save-coalition-values", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    period = args.period
    if period is None:
        period = int(os.getenv("SLURM_ARRAY_TASK_ID", "0"))
    workers = args.workers
    if workers is None:
        workers = int(os.getenv("SLURM_CPUS_PER_TASK", "1"))

    case_path = os.path.join(WORKFLOW_DIR, "data", f"case_example_dict_{args.case_tag}.pkl")
    case = load_case(case_path)
    n_agents = int(case["TG_num"] + case["RG_num"] + case["D_num"])
    total_masks = 1 << n_agents
    output_dir = os.path.join(WORKFLOW_DIR, "exact_shapley_data", args.case_tag)
    os.makedirs(output_dir, exist_ok=True)

    start = time.time()
    masks = np.arange(total_masks, dtype=np.uint64)
    chunks = [masks[i : i + args.chunk_size] for i in range(0, total_masks, args.chunk_size)]
    values = np.empty(total_masks, dtype=float)

    if workers <= 1:
        _init_worker(case_path, period)
        for chunk in chunks:
            chunk_masks, chunk_values = _evaluate_chunk(chunk)
            values[chunk_masks.astype(np.intp)] = chunk_values
    else:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, initargs=(case_path, period)) as executor:
            futures = [executor.submit(_evaluate_chunk, chunk) for chunk in chunks]
            for future in as_completed(futures):
                chunk_masks, chunk_values = future.result()
                values[chunk_masks.astype(np.intp)] = chunk_values

    origin_phi = exact_shapley_from_values(values, n_agents)
    merged_phi = merge_ess_roles(case, origin_phi)
    full_value = float(values[-1])
    empty_value = float(values[0])
    total_time = time.time() - start

    np.save(os.path.join(output_dir, f"exact_origin_{period}.npy"), origin_phi)
    np.save(os.path.join(output_dir, f"exact_merged_{period}.npy"), merged_phi)
    np.save(os.path.join(output_dir, f"exact_full_value_{period}.npy"), np.asarray(full_value))
    np.save(os.path.join(output_dir, f"exact_empty_value_{period}.npy"), np.asarray(empty_value))
    np.save(os.path.join(output_dir, f"exact_total_time_{period}.npy"), np.asarray(total_time))
    if args.save_coalition_values:
        np.save(os.path.join(output_dir, f"coalition_values_{period}.npy"), values)

    print(f"=== Exact Shapley period completed: case={args.case_tag}, t={period} ===")
    print("n_agents_origin:", n_agents)
    print("coalitions:", total_masks)
    print("origin_phi:", origin_phi)
    print("merged_phi:", merged_phi)
    print("sum_origin:", origin_phi.sum())
    print("full_value:", full_value)
    print("empty_value:", empty_value)
    print("efficiency_gap:", origin_phi.sum() - (full_value - empty_value))
    print("total_time_sec:", total_time)


if __name__ == "__main__":
    main()
