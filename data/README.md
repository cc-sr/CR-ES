# Data

## input_profiles

Processed load and renewable profile inputs used by the IEEE 14-bus, IEEE 30-bus, and IEEE 118-bus case studies.

## results/main_cases

Main-case result workbooks:

- `exact_shapley_ieee14_price_taking_base_24h.xlsx`: price-taking exact Shapley benchmark for the IEEE 14-bus case.
- `kernelshap_ieee14_price_taking_base_24h.xlsx`: corresponding 24-hour KernelSHAP result for the IEEE 14-bus case.
- `kernelshap_ieee30_manuscript_168h.xlsx`: 168-hour KernelSHAP result for the IEEE 30-bus manuscript case.

## results/diagnostic_cases

Retained diagnostic KernelSHAP workbooks, one prepared-case summary workbook, one participant intensity summary workbook, and prepared case files. The `metadata_*.json` files describe case settings and sampling parameters for the corresponding KernelSHAP runs.

## results/followup_cases

Follow-up result workbooks for the second-round cases:

- `kernelshap_ieee14_storage_location_bus45_24h.xlsx`
- `kernelshap_ieee14_storage_location_bus68_24h.xlsx`
- `kernelshap_ieee14_storage_location_bus23_24h.xlsx`
- `kernelshap_ieee14_storage_location_bus1214_24h.xlsx`
- `kernelshap_ieee14_renewable_6x_24h.xlsx`
- `kernelshap_ieee118_high_res_24h.xlsx`
