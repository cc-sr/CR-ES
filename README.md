# Shapley Value-Based Carbon Emission Responsibility Allocation in Power Systems with Energy Storage

This repository contains the data and computation code for reproducing the numerical results of the paper.

## 1. Paper Title

**Shapley Value-Based Carbon Emission Responsibility Allocation in Power Systems with Energy Storage**

## 2. Code Purpose

The code implements a carbon emission responsibility allocation workflow for power systems with energy storage.

Main functions:

- build IEEE 14-bus and IEEE 30-bus study cases;
- run unit commitment, energy storage scheduling, and DC OPF calculations;
- evaluate coalition-based carbon emissions;
- compute exact Shapley values for the small benchmark case;
- approximate Shapley values with KernelSHAP for larger cases;
- collect numerical outputs used for the paper's figures and tables.

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

| Task | Command | Output |
|---|---|---|
| Prepare exact Shapley benchmark scripts | `python gen_Shapley_value_t_multi.py` | Per-period scripts in `make_Shapley/` |
| Run exact Shapley benchmark | Run the generated scripts in `make_Shapley/` | Exact Shapley workbook |
| Prepare KernelSHAP scripts | `python gen_kernel_data_t_multi_RG.py` | Per-period scripts in `make_kernel_RG/` |
| Run KernelSHAP calculations | Run the generated scripts in `make_kernel_RG/` | Period-wise KernelSHAP `.npy` outputs |
| Collect KernelSHAP results | `python results_excel.py` | KernelSHAP Excel workbook |

For high-renewable/high-storage diagnostic experiments, use `programs/hpc_diagnostics/`. The SLURM workflow is documented in `programs/hpc_diagnostics/hpc_kernelshap_quickstart.md`.

## 7. Reproducing Figures and Tables

The plotting scripts and final figure PDFs are not included. Figures and tables can be reproduced from the uploaded Excel workbooks.

| Result file | Use |
|---|---|
| `data/results/main_cases/shapley_ieee14_exact_results.xlsx` | Exact Shapley benchmark and KernelSHAP comparison |
| `data/results/main_cases/kernelshap_ieee14_24h_scene3.xlsx` | IEEE 14-bus main KernelSHAP case |
| `data/results/main_cases/kernelshap_ieee30_168h_scene3.xlsx` | IEEE 30-bus seven-day KernelSHAP case |
| `data/results/diagnostic_cases/kernelSHAP_*.xlsx` | Retained diagnostic KernelSHAP storage and renewable cases |
| `data/results/diagnostic_cases/prepared_ieee14_required_case_summary.xlsx` | Prepared diagnostic case summary |
| `data/results/diagnostic_cases/all_participant_intensity_summary.xlsx` | Group- and participant-level intensity summaries |

Common workbook sheets:

- `SHAP_t`: hourly allocation results;
- `SHAP_t_origin`: hourly allocation before merging storage charging/discharging roles;
- `SHAP_all`: KernelSHAP estimates across sample checkpoints;
- `SHAP_total`: time-aggregated allocation after role merging;
- `SHAP_total_origin`: time-aggregated allocation before role merging;
- `ESS_decomposition`: storage charging responsibility, discharging credit, and net allocation;
- `efficiency_check`: allocation sum versus full-coalition emissions;
- `dispatch_summary`: operation summary for diagnostic cases;
- `group_intensity`, `participant_intensity`: retained diagnostic intensity summaries.

## 8. Data Sources

| Data type | Location or source |
|---|---|
| Network and participant parameters | Encoded in the case-construction scripts under `programs/main_workflow/` |
| IEEE 14-bus and IEEE 30-bus load/renewable profiles | Processed files in `data/input_profiles/` |
| Diagnostic case settings | `data/results/diagnostic_cases/metadata_*.json` |
| Main numerical outputs | `data/results/main_cases/` |
| Diagnostic numerical outputs | `data/results/diagnostic_cases/` |

The uploaded profile workbooks are processed inputs used by the case-study scripts.

## 9. Data Not Uploaded

The following files are not included in this repository:

- raw external time-series sources used to prepare the processed load and renewable profiles, because redistribution rights may be restricted;
- large per-period KernelSHAP `.npy` intermediate outputs;
- sampled-coalition folders generated during KernelSHAP runs;
- solver logs and temporary HPC output files;
- local trial folders and temporary run outputs;
- plotting scripts and final generated figure PDFs.

## 10. Contact

For questions about the code or data, please contact:

**Siru Chen**  
`chensiru@sjtu.edu.cn`

## 11. License

This repository is released under the MIT License. See `LICENSE` for details.
