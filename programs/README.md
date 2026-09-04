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

The IEEE 30-bus main data-preparation path is fixed to the retained manuscript
case.

## hpc_diagnostics

HPC workflow for IEEE 14-bus diagnostic KernelSHAP cases, the IEEE 14-bus exact Shapley benchmark, the storage-location cases, and the renewable-capacity cases including RE6x. It includes case preparation, per-period KernelSHAP and exact Shapley jobs, result collection, SLURM scripts, and operational workflow notes.

Key follow-up entry points:

- `prepare_ieee14_location_cases_24h.py --case-group location`
- `prepare_ieee14_location_cases_24h.py --case-group renewable`
- `slurm_prepare_price_taking_cases.sh`

## ieee118_high_res

IEEE 118-bus high-renewable workflow. It includes the MATPOWER topology file, processed-case builder, UC/ESS dispatch model, period-wise KernelSHAP evaluator, result collector, Excel exporter, and SLURM scripts.

Plotting scripts and generated figure files are intentionally excluded.
