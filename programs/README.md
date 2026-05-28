# Programs

## main_workflow

Local computation workflow for the main cases. It includes scripts for:

- IEEE case construction and profile loading
- UC and ESS scheduling
- DC OPF and carbon responsibility calculation
- exact Shapley calculation
- KernelSHAP sample generation and estimation
- result workbook generation

Core script names are preserved where they are used as Python imports by other
scripts.

## hpc_diagnostics

HPC workflow for diagnostic KernelSHAP cases. It includes case preparation,
per-period KernelSHAP jobs, result collection, SLURM scripts, and operational
workflow notes.

Plotting scripts and generated figure files are intentionally excluded.
