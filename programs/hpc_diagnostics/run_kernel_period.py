import argparse
import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from coalition_kernel_core import compute_period_kernel  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Run one period of conditional period-wise KernelSHAP.")
    parser.add_argument("--case-tag", required=True)
    parser.add_argument("--period", type=int, default=None)
    parser.add_argument("--kernel-num", type=int, default=3000)
    parser.add_argument("--samples-per-kernel", type=int, default=100)
    parser.add_argument("--checkpoint-every", type=int, default=5)
    parser.add_argument("--workers", type=int, default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    period = args.period
    if period is None:
        period = int(os.getenv("SLURM_ARRAY_TASK_ID", "0"))
    workers = args.workers
    if workers is None:
        workers = int(os.getenv("SLURM_CPUS_PER_TASK", "1"))

    base_dir = os.path.abspath(os.path.dirname(__file__))
    case_path = os.path.join(base_dir, "data", f"case_example_dict_{args.case_tag}.pkl")
    origin, merged, full_value, total_time = compute_period_kernel(
        case_path=case_path,
        case_tag=args.case_tag,
        period=period,
        kernel_num=args.kernel_num,
        samples_per_kernel=args.samples_per_kernel,
        checkpoint_every=args.checkpoint_every,
        workers=workers,
    )
    print(f"=== KernelSHAP period completed: case={args.case_tag}, t={period} ===")
    print("origin_phi:", origin)
    print("merged_phi:", merged)
    print("sum_origin:", origin.sum())
    print("full_value:", full_value)
    print("total_time_sec:", total_time)


if __name__ == "__main__":
    main()
