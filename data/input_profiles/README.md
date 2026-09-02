# Input Profiles

This folder contains the processed load and renewable profile inputs used by the
IEEE 14-bus and IEEE 30-bus case studies.

## Files

| File | Use |
|---|---|
| `ieee14_profile_data.xlsx` | Processed profiles used by the IEEE 14-bus case-construction scripts |
| `ieee30_profile_data.xlsx` | Processed profiles used by the IEEE 30-bus case-construction scripts |

## Workbook Format

Each workbook contains one sheet, `Sheet1`, with ten profile columns.

| Column positions | Meaning in the code |
|---|---|
| Columns 1-8 | Normalized load profile candidates |
| Columns 9-10 | Renewable availability profiles, read as `RG_cap` |

The values are processed normalized profiles rather than final MW quantities.
In the case-construction scripts, load profiles are multiplied by each bus
load's base demand (`D_P_base`), while renewable availability profiles are
multiplied by renewable capacity parameters (`RG_P`).

## Code Usage

The main scripts read these files from `data/input_profiles/`:

- `programs/main_workflow/make_ieee14_uc_opf_es.py`
- `programs/main_workflow/make_ieee30_uc_opf_es.py`

For the retained cases, the scripts use a fixed random seed (`1126`) to assign
the load profile columns to individual demand participants. Renewable profiles
are not stored in a separate file; they are the last two columns of the same
workbooks.

## Data Availability Note

This folder provides the processed load and renewable profile datasets actually
used by the manuscript case studies.
