"""Prepare the IEEE 14-bus location or renewable-capacity cases."""

import argparse
import os
import sys


WORKFLOW_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(WORKFLOW_DIR)

from prepare_price_taking_cases import (  # noqa: E402
    CASE_CONFIG,
    LOCATION_CASES,
    RENEWABLE_CASES,
    prepare_one,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Prepare the 24-hour IEEE14 price-taking cases."
    )
    parser.add_argument("--kernel-num", type=int, default=1000)
    parser.add_argument("--samples-per-kernel", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1126)
    parser.add_argument("--sceneid", type=int, default=3)
    parser.add_argument("--smoke-hours", type=int, default=24)
    parser.add_argument(
        "--case-group", choices=("location", "renewable", "all"), default="location"
    )
    parser.add_argument("--cases", nargs="+", choices=list(CASE_CONFIG), default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    os.makedirs(os.path.join(WORKFLOW_DIR, "data"), exist_ok=True)
    if args.cases is not None:
        case_tags = tuple(args.cases)
    elif args.case_group == "renewable":
        case_tags = RENEWABLE_CASES
    elif args.case_group == "all":
        case_tags = tuple(CASE_CONFIG)
    else:
        case_tags = LOCATION_CASES
    summaries = [prepare_one(tag, args) for tag in case_tags]

    import pandas as pd

    summary_df = pd.DataFrame(summaries)
    output_dir = os.path.join(WORKFLOW_DIR, "data")
    summary_stem = {
        "location": "prepared_ieee14_price_taking_location_summary",
        "renewable": "prepared_ieee14_price_taking_renewable_summary",
        "all": "prepared_ieee14_price_taking_all_summary",
    }
    if args.cases is not None:
        summary_name = "prepared_ieee14_price_taking_selected_summary"
    else:
        summary_name = summary_stem[args.case_group]
    output_path = os.path.join(output_dir, f"{summary_name}.xlsx")
    summary_df.to_excel(output_path, index=False)
    summary_df.to_csv(
        os.path.join(output_dir, f"{summary_name}.csv"),
        index=False,
    )
    print("Prepared IEEE14 24-hour price-taking cases:", output_path)
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
