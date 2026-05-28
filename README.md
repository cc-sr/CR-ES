# Shapley Value-Based Carbon Emission Responsibility Allocation in Power Systems with Energy Storage

This repository provides the data and computation programs for the manuscript
above. The code implements a multi-period carbon responsibility allocation
workflow for power systems with energy storage, including unit commitment,
storage scheduling, DC OPF-based coalition evaluation, exact Shapley
calculation for the small benchmark case, KernelSHAP approximation, and
diagnostic high-renewable/high-storage experiments.

## Repository Structure

```text
data/
  input_profiles/
  results/
    main_cases/
    diagnostic_cases/

programs/
  main_workflow/
  hpc_diagnostics/

requirements.txt
LICENSE
README.md
```

## Python Version

The repository was prepared with Python 3.12.3. Python 3.10 or newer is
recommended.

## Dependency Installation

Create and activate a virtual environment, then install the Python packages:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The optimization scripts use CVXPY with MOSEK, and some diagnostic scripts can
use Gurobi before falling back to MOSEK. A valid MOSEK license is required for
the main workflow. If Gurobi is used, a valid Gurobi license is also required.

## Running the Main Experiments

The main workflow scripts are in `programs/main_workflow/`.

Generate exact Shapley scripts for the IEEE 14-bus benchmark:

```bash
cd programs/main_workflow
python gen_Shapley_value_t_multi.py
```

This creates per-period scripts under `make_Shapley/`. Run those generated
scripts to compute the exact Shapley benchmark workbook.

Generate KernelSHAP scripts for the main IEEE case workflow:

```bash
cd programs/main_workflow
python gen_kernel_data_t_multi_RG.py
```

This creates per-period scripts under `make_kernel_RG/`. Run the generated
scripts to compute period-wise KernelSHAP outputs, then collect them into an
Excel workbook:

```bash
python results_excel.py
```

The high-renewable/high-storage diagnostic workflow is in
`programs/hpc_diagnostics/`. See
`programs/hpc_diagnostics/hpc_kernelshap_quickstart.md` for SLURM-based
preparation, per-period KernelSHAP jobs, and result collection.

## Reproducing Figures and Tables

The repository includes the numerical workbooks used to reproduce the paper's
tables and figure data:

- `data/results/main_cases/shapley_ieee14_exact_results.xlsx`
- `data/results/main_cases/kernelshap_ieee14_24h_scene3.xlsx`
- `data/results/main_cases/kernelshap_ieee30_168h_scene3.xlsx`
- `data/results/diagnostic_cases/kernelSHAP_*.xlsx`
- `data/results/diagnostic_cases/*sensitivity*.xlsx`
- `data/results/diagnostic_cases/all_participant_intensity_summary.xlsx`

Important sheets include `SHAP_t`, `SHAP_t_origin`, `SHAP_all`,
`SHAP_total`, `SHAP_total_origin`, `ESS_decomposition`,
`efficiency_check`, `dispatch_summary`, `summary`, `hourly_profile`, and
`SOC`, depending on the workbook.

Plotting scripts and final figure PDFs are not included in this repository.
Figures and tables can be reproduced by reading the uploaded Excel workbooks
and using the sheet names above.

## Data Sources

- Network, participant, generator, storage, and branch parameters for the IEEE
  14-bus and IEEE 30-bus studies are encoded in the case-construction scripts
  under `programs/main_workflow/`.
- Processed load and renewable profile inputs are provided in
  `data/input_profiles/ieee14_profile_data.xlsx` and
  `data/input_profiles/ieee30_profile_data.xlsx`.
- Diagnostic case settings and sampling parameters are documented in
  `data/results/diagnostic_cases/metadata_*.json`.
- Result workbooks in `data/results/` are the processed outputs used for the
  manuscript's numerical analysis.

## Data Not Uploaded

The raw external time-series sources used to prepare the processed load and
renewable profiles are not included because redistribution rights may be
restricted. Large generated intermediate files are also not uploaded, including
per-period KernelSHAP `.npy` outputs, sampled-coalition folders, solver logs,
temporary run directories, and trial outputs.

## Contact

For questions about the code or data, please contact:

- Siru Chen: `chensiru@sjtu.edu.cn`

## License

This repository is released under the MIT License. See `LICENSE` for details.
