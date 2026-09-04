# Shapley Value-Based Carbon Emission Responsibility Allocation in Power Systems with Energy Storage

This repository contains the processed data and computation code for reproducing the numerical results of the paper.

## 1. Paper Title

**Shapley Value-Based Carbon Emission Responsibility Allocation in Power Systems with Energy Storage**

## 2. Code Purpose

The code builds the IEEE 14-bus, IEEE 30-bus, and IEEE 118-bus study cases, runs UC/ESS/OPF calculations, evaluates coalition emissions, and computes exact Shapley or KernelSHAP carbon-responsibility allocations.

The repository is organized as a reproducibility package. It includes the case-building scripts, simulation and allocation programs, processed load and renewable profiles, and the retained result workbooks used for the manuscript and follow-up reviewer checks.

## 3. Repository Structure

| Path | Content |
|---|---|
| `data/input_profiles/` | Processed load and renewable profile inputs for the IEEE 14-bus, IEEE 30-bus, and IEEE 118-bus cases |
| `data/results/main_cases/` | Main-case Shapley and KernelSHAP result workbooks |
| `data/results/diagnostic_cases/` | Diagnostic KernelSHAP workbooks, metadata, prepared case files, and participant summary workbook |
| `data/results/followup_cases/` | IEEE 14-bus storage-location, IEEE 14-bus RE6x, and IEEE 118-bus high-renewable result workbooks |
| `programs/main_workflow/` | Local simulation, OPF, Shapley, KernelSHAP, and result-collection scripts |
| `programs/hpc_diagnostics/` | IEEE 14-bus diagnostic, storage-location, renewable-capacity, exact Shapley, KernelSHAP, and SLURM scripts |
| `programs/ieee118_high_res/` | IEEE 118-bus high-renewable case builder, dispatch model, KernelSHAP scripts, and SLURM scripts |
| `requirements.txt` | Required Python package list, with optional Gurobi note |
| `LICENSE` | MIT License |

## 4. Python Version

The repository was checked with **Python 3.11.11** on macOS. Python **3.10 or newer** is recommended.

## 5. Dependency Installation

Install the Python packages from `requirements.txt`.

Basic setup:

1. Create a virtual environment: `python -m venv .venv`
2. Activate it on macOS/Linux: `source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`

The optimization scripts use CVXPY with MOSEK. A valid MOSEK license is required to rerun the main optimization workflow and the KernelSHAP coalition evaluations.

Gurobi is optional. Some UC/diagnostic paths can use Gurobi when `gurobipy` and a valid Gurobi license are available, but the retained workflow does not require it.

## 6. Running the Main Experiments

### IEEE 14-bus and IEEE 30-bus Local Workflow

Run the local manuscript workflow from `programs/main_workflow/`. The retained local manuscript path includes the IEEE 14-bus exact Shapley/KernelSHAP benchmark and the IEEE 30-bus seven-day KernelSHAP case.

Enter the workflow directory first: `cd programs/main_workflow`.

| Task | Command | Output |
|---|---|---|
| Build case data and random coalition samples | Called automatically by the generation scripts through `make_data.py` | Case pickle files in `data/` and random samples in `random_S_set/` |
| Prepare exact Shapley benchmark scripts | `python gen_Shapley_value_t_multi.py` | Per-period scripts in `make_Shapley/` and initial workbook in `Shapley_value_results/` |
| Run exact Shapley benchmark | Run the generated scripts in `make_Shapley/` | Completed exact Shapley workbook |
| Prepare KernelSHAP scripts | `python gen_kernel_data_t_multi_RG.py` | Per-period scripts in `make_kernel_RG/` |
| Run KernelSHAP calculations | Run the generated scripts in `make_kernel_RG/` | Period-wise KernelSHAP `.npy` outputs |
| Collect KernelSHAP results | `python results_excel.py` | KernelSHAP Excel workbook |

Generated local outputs are written under `programs/main_workflow/data/`, `programs/main_workflow/random_S_set/`, `programs/main_workflow/make_Shapley/`, `programs/main_workflow/make_kernel_RG/`, `programs/main_workflow/Shapley_value_results/`, `programs/main_workflow/kernel_data_RG/`, and `programs/main_workflow/kernel_SHAP_results/`. These generated files are ignored by Git.

### IEEE 14-bus Exact Shapley and Follow-up KernelSHAP Cases

Use `programs/hpc_diagnostics/` for the IEEE 14-bus price-taking exact Shapley benchmark, the storage-location cases, and the renewable-capacity cases including RE6x.

| Task | Command | Output |
|---|---|---|
| Prepare price-taking cases | `python prepare_price_taking_cases.py --cases PT14_BASE_2h` | Case file, metadata, and random samples |
| Run one exact period | `python run_exact_shapley_period.py --case-tag PT14_BASE_2h --period 0` | Period-level exact Shapley `.npy` files |
| Collect exact results | `python collect_exact_shapley_results.py --case-tag PT14_BASE_2h` | Exact Shapley Excel workbook |
| Prepare storage-location cases | `python prepare_ieee14_location_cases_24h.py --case-group location` | Four 24-hour storage-location case files |
| Prepare renewable-capacity cases | `python prepare_ieee14_location_cases_24h.py --case-group renewable` | Four 24-hour renewable-capacity case files, including `PT14_RG6x_8h` |
| Run one KernelSHAP period | `python run_kernel_period.py --case-tag PT14_RG6x_8h --period 0` | One period-level KernelSHAP output |
| Collect KernelSHAP results | `python collect_kernel_results.py --case-tag PT14_RG6x_8h --expected-periods 24` | Final KernelSHAP workbook |

For HPC runs, use the SLURM scripts in the same directory. The scripts default to `CONDA_ENV=cr-es`; set `HPC_HOME`, `CONDA_ENV`, `MOSEKLM_LICENSE_FILE`, or `PROJECT_DIR` before `sbatch` if your cluster paths differ.

### IEEE 118-bus High-renewable Case

Use `programs/ieee118_high_res/` for the IEEE 118-bus high-renewable case.

| Task | Command | Output |
|---|---|---|
| Prepare the 24-hour case | `python prepare_ieee118_price_taking_case.py` | Case settings, dispatch summary, UC/SOC trajectory, metadata, and random samples |
| Run one KernelSHAP period | `python run_kernel_period.py --period 0` | One period-level KernelSHAP output |
| Collect KernelSHAP results | `python collect_kernel_results.py --expected-periods 24` | Final KernelSHAP workbook |

For HPC runs, use `slurm_prepare_ieee118.sh`, `slurm_kernel_ieee118_array.sh`, and `slurm_collect_ieee118.sh`.

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
| `data/results/followup_cases/kernelshap_ieee14_storage_location_*.xlsx` | IEEE 14-bus storage-location sensitivity results |
| `data/results/followup_cases/kernelshap_ieee14_renewable_6x_24h.xlsx` | IEEE 14-bus RE6x renewable-capacity result |
| `data/results/followup_cases/kernelshap_ieee118_high_res_24h.xlsx` | IEEE 118-bus high-renewable result |

The Excel workbooks contain the hourly and aggregated allocation results, KernelSHAP error metrics, ESS decomposition, efficiency checks, dispatch summaries, and participant-intensity summaries used by the manuscript tables and figures. The processed load and renewable profiles used to draw the input-profile figure are in `data/input_profiles/`.

## 8. Data Sources

| Data type | Location |
|---|---|
| IEEE 14-bus and IEEE 30-bus network and participant parameters | Encoded in the case-construction scripts under `programs/main_workflow/` |
| IEEE 118-bus network topology | `programs/ieee118_high_res/case118.m` |
| Load and renewable profiles actually used by the paper cases | Processed datasets in `data/input_profiles/` |
| Numerical outputs and diagnostic metadata | `data/results/` |

## 9. Data Not Uploaded

Not uploaded: large intermediate `.npy` arrays, sampled-coalition folders, solver/HPC logs, local trial outputs, plotting scripts, and generated figure PDFs.

## 10. Contact

For questions about the code or data, please contact:

**Siru Chen**  
`chensiru@sjtu.edu.cn`

## 11. License

This repository is released under the MIT License. See `LICENSE` for details.
