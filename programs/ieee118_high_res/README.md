# IEEE118 high-RES 24-hour case

This package uses the IEEE 118-bus high-renewable case with the retained LMP-based price-taking workflow. The RES entries are aggregated wind and solar resource portfolios connected at selected buses; their capacities are equivalent nodal capacities rather than individual physical plant sizes.

Default case tag:

`PT118_ADJ_coal45_gas20_res300_one_local_fixedthermal_4h`

The default settings are:

- 24-hour horizon, one-hour resolution, day 300, load scale 1.0, seed 1126;
- RES injection buses 54, 65, 80, and 89;
- RES capacity reference buses 10, 65, 80, and 89;
- RES capacity target 3.0 times the realized peak load, rounded to 10 MW;
- ESS at buses 59, 90, 116, and 54, with 110 MW and 440 MWh per unit;
- ESS duration 4 h and total ESS size 440 MW/1760 MWh;
- thermal capacity scales of 0.45 for coal and 0.20 for gas;
- 500 MW active-branch limit and penalty coefficients 5000/100/200 for load shedding, renewable curtailment, and thermal curtailment.

The topology is read from `case118.m`. The processed load and renewable profiles are read from `../../data/input_profiles/ieee118_profile_data.xlsx`.

Prepare the case and its 24-hour UC/SOC trajectory with `python prepare_ieee118_price_taking_case.py`.

The generated settings, stage-1 summary, UC, dispatch, ESS charging, discharging, and SOC files are written to `data/`. KernelSHAP period results are collected into `kernel_SHAP_results/`.

For HPC runs, submit `slurm_prepare_ieee118.sh`, then the 24-period array `slurm_kernel_ieee118_array.sh`, and finally `slurm_collect_ieee118.sh`.
