# HPC KernelSHAP Quickstart

This file keeps only the short HPC operation path for the IEEE 14-bus cases.

Default working directory: `programs/hpc_diagnostics`.

Before submitting jobs, enter the directory after uploading the repo:

`cd /path/to/CR-ES/programs/hpc_diagnostics`

If a different layout is used, set:

`export PROJECT_DIR=$(pwd)`

The SLURM scripts default to `CONDA_ENV=cr-es`. Set `HPC_HOME`, `CONDA_ENV`, or `MOSEKLM_LICENSE_FILE` before `sbatch` if needed.

## 1. Prepare Case Inputs

Legacy storage-size sensitivity:

- `CASE_TAG=ES40_30MW EXPERIMENT=storage DAYS=3 sbatch slurm_prepare_case.sh`
- `CASE_TAG=ES80_60MW EXPERIMENT=storage DAYS=3 sbatch slurm_prepare_case.sh`
- `CASE_TAG=ES130_110MW EXPERIMENT=storage DAYS=3 sbatch slurm_prepare_case.sh`

Legacy renewable-capacity sensitivity:

- `CASE_TAG=RGcap0xPeak_ES40_30MW EXPERIMENT=renewable DAYS=1 sbatch slurm_prepare_case.sh`
- `CASE_TAG=RGcap2xPeak_ES40_30MW EXPERIMENT=renewable DAYS=1 sbatch slurm_prepare_case.sh`
- `CASE_TAG=RGcap3xPeak_ES40_30MW EXPERIMENT=renewable DAYS=1 sbatch slurm_prepare_case.sh`

IEEE 14-bus storage-location sensitivity:

- `CASE_GROUP=location sbatch slurm_prepare_price_taking_cases.sh`

IEEE 14-bus renewable-capacity sensitivity including RE6x:

- `CASE_GROUP=renewable sbatch slurm_prepare_price_taking_cases.sh`
- `CASE_TAGS="PT14_RG6x_8h" sbatch slurm_prepare_price_taking_cases.sh`

## 2. Submit KernelSHAP Jobs

Storage-size sensitivity has 72 periods:

- `CASE_TAG=ES40_30MW KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch slurm_kernel_array.sh`
- `CASE_TAG=ES80_60MW KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch slurm_kernel_array.sh`
- `CASE_TAG=ES130_110MW KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch slurm_kernel_array.sh`

The renewable-capacity and storage-location cases have 24 periods:

- `CASE_TAG=RGcap0xPeak_ES40_30MW KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch --array=0-23 slurm_kernel_array.sh`
- `CASE_TAG=RGcap2xPeak_ES40_30MW KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch --array=0-23 slurm_kernel_array.sh`
- `CASE_TAG=RGcap3xPeak_ES40_30MW KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch --array=0-23 slurm_kernel_array.sh`
- `CASE_TAG=PT14_LOC_45 KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch --array=0-23 slurm_kernel_array.sh`
- `CASE_TAG=PT14_LOC_68 KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch --array=0-23 slurm_kernel_array.sh`
- `CASE_TAG=PT14_LOC_23 KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch --array=0-23 slurm_kernel_array.sh`
- `CASE_TAG=PT14_LOC_1214 KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch --array=0-23 slurm_kernel_array.sh`
- `CASE_TAG=PT14_RG6x_8h KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch --array=0-23 slurm_kernel_array.sh`

## 3. Collect Results

- `CASE_TAG=ES40_30MW EXPECTED_PERIODS=72 sbatch slurm_collect_results.sh`
- `CASE_TAG=ES80_60MW EXPECTED_PERIODS=72 sbatch slurm_collect_results.sh`
- `CASE_TAG=ES130_110MW EXPECTED_PERIODS=72 sbatch slurm_collect_results.sh`
- `CASE_TAG=RGcap0xPeak_ES40_30MW EXPECTED_PERIODS=24 sbatch slurm_collect_results.sh`
- `CASE_TAG=RGcap2xPeak_ES40_30MW EXPECTED_PERIODS=24 sbatch slurm_collect_results.sh`
- `CASE_TAG=RGcap3xPeak_ES40_30MW EXPECTED_PERIODS=24 sbatch slurm_collect_results.sh`
- `CASE_TAG=PT14_LOC_45 EXPECTED_PERIODS=24 sbatch slurm_collect_results.sh`
- `CASE_TAG=PT14_LOC_68 EXPECTED_PERIODS=24 sbatch slurm_collect_results.sh`
- `CASE_TAG=PT14_LOC_23 EXPECTED_PERIODS=24 sbatch slurm_collect_results.sh`
- `CASE_TAG=PT14_LOC_1214 EXPECTED_PERIODS=24 sbatch slurm_collect_results.sh`
- `CASE_TAG=PT14_RG6x_8h EXPECTED_PERIODS=24 sbatch slurm_collect_results.sh`

Final Excel workbooks are generated in `programs/hpc_diagnostics/kernel_SHAP_results/`. Period-level temporary outputs are generated in `programs/hpc_diagnostics/kernel_data/`.

These output directories are ignored by Git.
