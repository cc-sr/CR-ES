# Input Profiles

This folder provides the processed load and renewable profile datasets actually used by the IEEE 14-bus, IEEE 30-bus, and IEEE 118-bus case studies.

| File | Used by |
|---|---|
| `ieee14_profile_data.xlsx` | IEEE 14-bus main, diagnostic, storage-location, and renewable-capacity scripts |
| `ieee30_profile_data.xlsx` | IEEE 30-bus manuscript case scripts |
| `ieee118_profile_data.xlsx` | IEEE 118-bus high-renewable case scripts |

## IEEE 14-bus and IEEE 30-bus Workbooks

| Columns in `Sheet1` | Meaning |
|---|---|
| Columns 1-8 | Normalized load profile candidates |
| Columns 9-10 | Renewable availability profiles, read as `RG_cap` |

The case-construction scripts multiply these normalized series by the load base demand (`D_P_base`) or renewable capacity (`RG_P`) parameters.

These files are read by `programs/main_workflow/make_ieee14_uc_opf_es.py`, `programs/main_workflow/make_ieee30_uc_opf_es.py`, and the IEEE 14-bus scripts under `programs/hpc_diagnostics/`.

## IEEE 118-bus Workbook

`ieee118_profile_data.xlsx` provides the processed time-series profile pool used by `programs/ieee118_high_res/ieee118_case_builder.py`. The first eight columns are normalized load profile candidates; the last two columns are renewable availability profiles.
