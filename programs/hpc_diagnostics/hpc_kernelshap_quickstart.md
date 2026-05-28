# HPC KernelSHAP Quickstart

这份文档只保留最短操作路径。默认你已经把整个 Repo 上传到了 HPC，例如：

```text
/dssg/home/acct-seed/chensiru/carbon/es/CR-ES
```

HPC 计算目录为：

```text
programs/hpc_diagnostics
```

## 1. 进入计算目录

```bash
cd /dssg/home/acct-seed/chensiru/carbon/es/CR-ES/programs/hpc_diagnostics
```

如需使用其他位置，可以在提交任务前设置：

```bash
export PROJECT_DIR=$(pwd)
```

## 2. 准备 case 输入

储能敏感性：

```bash
CASE_TAG=ES40_30MW EXPERIMENT=storage DAYS=3 sbatch slurm_prepare_case.sh
CASE_TAG=ES80_60MW EXPERIMENT=storage DAYS=3 sbatch slurm_prepare_case.sh
CASE_TAG=ES130_110MW EXPERIMENT=storage DAYS=3 sbatch slurm_prepare_case.sh
```

新能源敏感性：

```bash
CASE_TAG=RGcap0xPeak_ES40_30MW EXPERIMENT=renewable DAYS=1 sbatch slurm_prepare_case.sh
CASE_TAG=RGcap2xPeak_ES40_30MW EXPERIMENT=renewable DAYS=1 sbatch slurm_prepare_case.sh
CASE_TAG=RGcap3xPeak_ES40_30MW EXPERIMENT=renewable DAYS=1 sbatch slurm_prepare_case.sh
```

## 3. 提交 KernelSHAP 任务

储能敏感性是 72 个时段：

```bash
CASE_TAG=ES40_30MW KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch slurm_kernel_array.sh
CASE_TAG=ES80_60MW KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch slurm_kernel_array.sh
CASE_TAG=ES130_110MW KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch slurm_kernel_array.sh
```

新能源敏感性是 24 个时段：

```bash
CASE_TAG=RGcap0xPeak_ES40_30MW KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch --array=0-23 slurm_kernel_array.sh
CASE_TAG=RGcap2xPeak_ES40_30MW KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch --array=0-23 slurm_kernel_array.sh
CASE_TAG=RGcap3xPeak_ES40_30MW KERNEL_NUM=1000 SAMPLES_PER_KERNEL=100 sbatch --array=0-23 slurm_kernel_array.sh
```

## 4. 收集结果

```bash
CASE_TAG=ES40_30MW EXPECTED_PERIODS=72 sbatch slurm_collect_results.sh
CASE_TAG=ES80_60MW EXPECTED_PERIODS=72 sbatch slurm_collect_results.sh
CASE_TAG=ES130_110MW EXPECTED_PERIODS=72 sbatch slurm_collect_results.sh

CASE_TAG=RGcap0xPeak_ES40_30MW EXPECTED_PERIODS=24 sbatch slurm_collect_results.sh
CASE_TAG=RGcap2xPeak_ES40_30MW EXPECTED_PERIODS=24 sbatch slurm_collect_results.sh
CASE_TAG=RGcap3xPeak_ES40_30MW EXPECTED_PERIODS=24 sbatch slurm_collect_results.sh
```

最终 Excel 默认生成在：

```text
programs/hpc_diagnostics/kernel_SHAP_results/
```

临时逐时段结果默认生成在：

```text
programs/hpc_diagnostics/kernel_data/
```

这些输出目录已写入 `.gitignore`，不会进入 Repo。
