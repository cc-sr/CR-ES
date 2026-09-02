# Input Profiles

This folder provides the processed load and renewable profile datasets actually used by the IEEE 14-bus and IEEE 30-bus manuscript case studies.

| File | Used by |
|---|---|
| `ieee14_profile_data.xlsx` | IEEE 14-bus case scripts |
| `ieee30_profile_data.xlsx` | IEEE 30-bus case scripts |

| Columns in `Sheet1` | Meaning |
|---|---|
| Columns 1-8 | Normalized load profile candidates |
| Columns 9-10 | Renewable availability profiles, read as `RG_cap` |

The case-construction scripts multiply these normalized series by the load base demand (`D_P_base`) or renewable capacity (`RG_P`) parameters.

These files are read by `programs/main_workflow/make_ieee14_uc_opf_es.py` and `programs/main_workflow/make_ieee30_uc_opf_es.py`.
