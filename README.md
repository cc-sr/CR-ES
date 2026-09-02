# Shapley Value-Based Carbon Emission Responsibility Allocation in Power Systems with Energy Storage

This repository contains the data and computation code for reproducing the numerical results of the paper.

## 1. Paper Title

**Shapley Value-Based Carbon Emission Responsibility Allocation in Power Systems with Energy Storage**

## 2. Code Purpose

The code builds the IEEE 14-bus and IEEE 30-bus study cases, runs UC/ESS/OPF
calculations, evaluates coalition emissions, and computes exact Shapley or
KernelSHAP carbon-responsibility allocations.

## 3. Repository Structure

| Path | Content |
|---|---|
| `data/input_profiles/` | Processed load and renewable profile inputs for the IEEE 14-bus and IEEE 30-bus cases |
| `data/results/main_cases/` | Main-case Shapley and KernelSHAP result workbooks |
| `data/results/diagnostic_cases/` | Diagnostic KernelSHAP workbooks, metadata, prepared case files, and participant summary workbook |
| `programs/main_workflow/` | Local simulation, OPF, Shapley, KernelSHAP, and result-collection scripts |
| `programs/hpc_diagnostics/` | HPC diagnostic KernelSHAP workflow and SLURM scripts |
| `requirements.txt` | Required Python package list, with optional Gurobi note |
| `LICENSE` | MIT License |

## 4. Python Version

The repository was prepared with **Python 3.12.3**.

Recommended version: **Python 3.10 or newer**.

## 5. Dependency Installation

Install the Python packages from `requirements.txt`.

Suggested setup:

1. Create a virtual environment: `python -m venv .venv`
2. Activate it on macOS/Linux: `source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`

The optimization scripts use CVXPY with MOSEK. A valid MOSEK license is required to rerun the main optimization workflow.

Gurobi is optional. Some diagnostic scripts can try Gurobi first and then fall back to MOSEK. If you want to use the Gurobi path, install `gurobipy` separately and make sure a valid Gurobi license is available.

## 6. Running the Main Experiments

Run the main workflow from `programs/main_workflow/`.

The retained IEEE 30-bus manuscript workflow uses the calibrated manuscript
case. The main data preparation helpers default to this retained case.

| Task | Command | Output |
|---|---|---|
| Prepare exact Shapley benchmark scripts | `python gen_Shapley_value_t_multi.py` | Per-period scripts in `make_Shapley/` |
| Run exact Shapley benchmark | Run the generated scripts in `make_Shapley/` | Exact Shapley workbook |
| Prepare KernelSHAP scripts | `python gen_kernel_data_t_multi_RG.py` | Per-period scripts in `make_kernel_RG/` |
| Run KernelSHAP calculations | Run the generated scripts in `make_kernel_RG/` | Period-wise KernelSHAP `.npy` outputs |
| Collect KernelSHAP results | `python results_excel.py` | KernelSHAP Excel workbook |

For high-renewable/high-storage diagnostic experiments, use `programs/hpc_diagnostics/`. The SLURM workflow is documented in `programs/hpc_diagnostics/hpc_kernelshap_quickstart.md`.

For the IEEE 14-bus price-taking exact Shapley benchmark, use `programs/hpc_diagnostics/`:

| Task | Command | Output |
|---|---|---|
| Prepare price-taking cases | `python prepare_price_taking_cases.py --cases PT14_BASE_2h` | Case file, metadata, and random samples |
| Run one exact period | `python run_exact_shapley_period.py --case-tag PT14_BASE_2h --period 0` | Period-level exact Shapley `.npy` files |
| Collect exact results | `python collect_exact_shapley_results.py --case-tag PT14_BASE_2h` | Exact Shapley Excel workbook |

## 7. Reproducing Figures and Tables

The plotting scripts and final figure PDFs are not included. Figures and tables can be reproduced from the uploaded Excel workbooks.

| Result file | Use |
|---|---|
| `data/results/main_cases/exact_shapley_ieee14_price_taking_base_24h.xlsx` | IEEE 14-bus price-taking exact Shapley benchmark and KernelSHAP comparison metrics |
| `data/results/main_cases/kernelshap_ieee14_price_taking_base_24h.xlsx` | Corresponding IEEE 14-bus price-taking KernelSHAP case |
| `data/results/main_cases/kernelshap_ieee30_manuscript_168h.xlsx` | IEEE 30-bus seven-day KernelSHAP case |
| `data/results/diagnostic_cases/kernelSHAP_*.xlsx` | Retained diagnostic KernelSHAP storage and renewable cases |
| `data/results/diagnostic_cases/prepared_ieee14_required_case_summary.xlsx` | Prepared diagnostic case summary |
| `data/results/diagnostic_cases/all_participant_intensity_summary.xlsx` | Group- and participant-level intensity summaries |

The Excel workbooks contain the hourly and aggregated allocation results,
KernelSHAP error metrics, ESS decomposition, efficiency checks, dispatch
summaries, and participant-intensity summaries used by the manuscript tables and
figures.

## 8. Data Sources

| Data type | Location |
|---|---|
| Network and participant parameters | Encoded in the case-construction scripts under `programs/main_workflow/` |
| IEEE 14-bus and IEEE 30-bus load/renewable profiles | Processed datasets in `data/input_profiles/` |
| Numerical outputs and diagnostic metadata | `data/results/` |

## 9. Data Not Uploaded

Not uploaded: large intermediate `.npy` arrays, sampled-coalition folders,
solver/HPC logs, local trial outputs, plotting scripts, and generated figure
PDFs.

## 10. Contact

For questions about the code or data, please contact:

**Siru Chen**  
`chensiru@sjtu.edu.cn`

## 11. License

This repository is released under the MIT License. See `LICENSE` for details.
