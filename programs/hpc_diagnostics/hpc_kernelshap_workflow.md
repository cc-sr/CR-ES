# IEEE14 KernelSHAP Workflow

本文档说明 IEEE 14-bus 诊断、储能位置和新能源容量算例的文件结构和运行边界。Repo 中保留的是正式计算所需脚本和已整理数据；本地 trial、临时日志、逐时段中间输出和画图脚本不进入仓库。

## Directory Layout

`programs/hpc_diagnostics` 中的脚本会从 `data/input_profiles/ieee14_profile_data.xlsx` 读取处理后的负荷和新能源 profile，并从 `programs/main_workflow/` 调用 IEEE14 建模和 PTDF helper。

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

储能位置敏感性：

| Case tag | ESS buses | Horizon |
|---|---|---:|
| `PT14_LOC_45` | 4, 5 | 24 h |
| `PT14_LOC_68` | 6, 8 | 24 h |
| `PT14_LOC_23` | 2, 3 | 24 h |
| `PT14_LOC_1214` | 12, 14 | 24 h |

新能源容量 follow-up：

| Case tag | Setting | Horizon |
|---|---|---:|
| `PT14_RG0x_8h` | 0x renewable capacity, 8 h ESS | 24 h |
| `PT14_RG2x_8h` | 2x renewable capacity, 8 h ESS | 24 h |
| `PT14_RG4x_8h` | 4x renewable capacity, 8 h ESS | 24 h |
| `PT14_RG6x_8h` | 6x renewable capacity, 8 h ESS | 24 h |

## Main Scripts

- `prepare_shapley_cases.py`: prepare case dictionaries, metadata, and sampled coalitions.
- `prepare_price_taking_cases.py`: prepare IEEE14 price-taking location and renewable-capacity cases.
- `prepare_ieee14_location_cases_24h.py`: compact entry point for the 24-hour location and renewable-capacity cases.
- `run_kernel_period.py`: run one period of coalition KernelSHAP evaluation.
- `collect_kernel_results.py`: collect period outputs into final Excel workbooks.
- `coalition_kernel_core.py`: shared KernelSHAP computation utilities.
- `ieee14_dispatch_model.py`: IEEE14 diagnostic dispatch and case-building model.

## SLURM Scripts

- `slurm_prepare_case.sh`
- `slurm_prepare_price_taking_cases.sh`
- `slurm_kernel_array.sh`
- `slurm_collect_results.sh`

The SLURM scripts default `PROJECT_DIR` to the directory containing the script and `CONDA_ENV` to `cr-es`. If the HPC layout is different, set `PROJECT_DIR`, `HPC_HOME`, `CONDA_ENV`, or `MOSEKLM_LICENSE_FILE` before submitting jobs.

## Output Boundary

Formal diagnostic outputs are the Excel workbooks under `data/results/diagnostic_cases/`. The follow-up storage-location and RE6x workbooks are under `data/results/followup_cases/`.

New HPC runs may generate:

`programs/hpc_diagnostics/data/`, `programs/hpc_diagnostics/random_S_set/`, `programs/hpc_diagnostics/kernel_data/`, and `programs/hpc_diagnostics/kernel_SHAP_results/`.

These generated directories are ignored by Git unless a specific result is selected and moved into `data/results/diagnostic_cases/` or `data/results/followup_cases/`.
