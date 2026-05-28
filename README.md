# CR-ES

This repository contains the data and computation programs associated with the
CR-ES / SEGAN revision package prepared on 2026-05-28.

## Repository Layout

```text
data/
  input_profiles/
  results/
    main_cases/
    diagnostic_cases/

programs/
  main_workflow/
  hpc_diagnostics/

README.md
```

## Main Contents

- `data/input_profiles/`: IEEE 14-bus and IEEE 30-bus load and renewable
  profile inputs.
- `data/results/main_cases/`: exact Shapley and KernelSHAP workbooks used for
  the main IEEE 14-bus and IEEE 30-bus cases.
- `data/results/diagnostic_cases/`: diagnostic storage and renewable
  sensitivity results, prepared case dictionaries, and metadata.
- `programs/main_workflow/`: local UC/ESS scheduling, OPF, Shapley, KernelSHAP,
  and result workbook generation scripts.
- `programs/hpc_diagnostics/`: HPC-oriented diagnostic KernelSHAP workflow and
  SLURM job scripts.
