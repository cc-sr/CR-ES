# IEEE14 Diagnostic KernelSHAP Workflow

本文档说明本轮诊断计算的文件结构和运行边界。Repo 中保留的是正式计算所需脚本和已整理数据；本地 trial、临时日志、逐时段中间输出和画图脚本不进入仓库。

## Directory Layout

```text
CR-ES/
  data/
    input_profiles/
    results/
      diagnostic_cases/
  programs/
    hpc_diagnostics/
    main_workflow/
```

`programs/hpc_diagnostics` 中的脚本会从 `data/input_profiles/` 读取
`ieee14_profile_data.xlsx`，并从 `programs/main_workflow/` 调用 IEEE14 建模和 PTDF helper。

## Cases

储能敏感性：

| Case tag | ES1 | ES2 | Horizon |
|---|---:|---:|---:|
| `ES40_30MW` | 40 MW / 160 MWh | 30 MW / 120 MWh | 72 h |
| `ES80_60MW` | 80 MW / 320 MWh | 60 MW / 240 MWh | 72 h |
| `ES130_110MW` | 130 MW / 520 MWh | 110 MW / 440 MWh | 72 h |

新能源容量敏感性：

| Case tag | Horizon |
|---|---:|
| `RGcap0xPeak_ES40_30MW` | 24 h |
| `RGcap2xPeak_ES40_30MW` | 24 h |
| `RGcap3xPeak_ES40_30MW` | 24 h |

## Main Scripts

- `prepare_shapley_cases.py`: prepare case dictionaries, metadata, and sampled coalitions.
- `run_kernel_period.py`: run one period of coalition KernelSHAP evaluation.
- `collect_kernel_results.py`: collect period outputs into final Excel workbooks.
- `coalition_kernel_core.py`: shared KernelSHAP computation utilities.
- `ieee14_dispatch_model.py`: IEEE14 diagnostic dispatch and case-building model.

## SLURM Scripts

- `slurm_prepare_case.sh`
- `slurm_kernel_array.sh`
- `slurm_collect_results.sh`

The SLURM scripts default `PROJECT_DIR` to the directory containing the script.
If the HPC layout is different, set `PROJECT_DIR` before submitting jobs.

## Output Boundary

Formal diagnostic outputs are the Excel workbooks under:

```text
data/results/diagnostic_cases/
```

New HPC runs may generate:

```text
programs/hpc_diagnostics/data/
programs/hpc_diagnostics/random_S_set/
programs/hpc_diagnostics/kernel_data/
programs/hpc_diagnostics/kernel_SHAP_results/
```

These generated directories are intentionally ignored by Git unless a specific
result is selected and moved into `data/results/diagnostic_cases/`.
