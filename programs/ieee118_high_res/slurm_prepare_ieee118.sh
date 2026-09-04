#!/bin/bash
#SBATCH --job-name=prep_i118
#SBATCH --output=slurm-%x-%A.out
#SBATCH --error=slurm-%x-%A.err
#SBATCH --time=02:00:00
#SBATCH --partition=64c512g
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4

HPC_HOME=${HPC_HOME:-$HOME}
if [[ -f "${HPC_HOME}/.bashrc" ]]; then
  source "${HPC_HOME}/.bashrc"
fi
CONDA_ENV=${CONDA_ENV:-cr-es}
conda activate ${CONDA_ENV}

export PATH=$(conda info --base)/envs/${CONDA_ENV}/bin:$PATH
export LD_LIBRARY_PATH=$(conda info --base)/envs/${CONDA_ENV}/lib:${LD_LIBRARY_PATH:-}
export MOSEKLM_LICENSE_FILE=${MOSEKLM_LICENSE_FILE:-${HPC_HOME}/mosek.lic}
export MOSEK_NUM_THREADS=1
export SOLVER_THREADS=${SOLVER_THREADS:-4}

PROJECT_DIR=${PROJECT_DIR:-$(cd "$(dirname "$0")" && pwd)}
CASE_TAG=${CASE_TAG:-PT118_ADJ_coal45_gas20_res300_one_local_fixedthermal_4h}
DAYS=${DAYS:-1}
DAY_OF_INTEREST=${DAY_OF_INTEREST:-300}
LOAD_SCALE=${LOAD_SCALE:-1.0}
RENEWABLE_BUSES=${RENEWABLE_BUSES:-54,65,80,89}
RENEWABLE_CAPACITY_REFERENCE_BUSES=${RENEWABLE_CAPACITY_REFERENCE_BUSES:-10,65,80,89}
RENEWABLE_CAPACITY_TO_PEAK=${RENEWABLE_CAPACITY_TO_PEAK:-3.0}
ESS_BUSES=${ESS_BUSES:-59,90,116,54}
ESS_POWER_TO_PEAK=${ESS_POWER_TO_PEAK:-0.15}
ESS_DURATION_H=${ESS_DURATION_H:-4.0}
BRANCH_LIMIT_MW=${BRANCH_LIMIT_MW:-500.0}
BRANCH_LIMIT_OVERRIDES=${BRANCH_LIMIT_OVERRIDES:-}
COAL_CAPACITY_SCALE=${COAL_CAPACITY_SCALE:-0.45}
GAS_CAPACITY_SCALE=${GAS_CAPACITY_SCALE:-0.20}
CAPACITY_ROUNDING_MW=${CAPACITY_ROUNDING_MW:-10.0}
KERNEL_NUM=${KERNEL_NUM:-5000}
SAMPLES_PER_KERNEL=${SAMPLES_PER_KERNEL:-100}
SEED=${SEED:-1126}
SMOKE_HOURS=${SMOKE_HOURS:-24}

python ${PROJECT_DIR}/prepare_ieee118_price_taking_case.py \
  --case-tag ${CASE_TAG} \
  --days ${DAYS} \
  --day-of-interest ${DAY_OF_INTEREST} \
  --load-scale ${LOAD_SCALE} \
  --renewable-buses ${RENEWABLE_BUSES} \
  --renewable-capacity-reference-buses ${RENEWABLE_CAPACITY_REFERENCE_BUSES} \
  --renewable-capacity-to-peak ${RENEWABLE_CAPACITY_TO_PEAK} \
  --ess-buses ${ESS_BUSES} \
  --ess-power-to-peak ${ESS_POWER_TO_PEAK} \
  --ess-duration-h ${ESS_DURATION_H} \
  --branch-limit-mw ${BRANCH_LIMIT_MW} \
  --branch-limit-overrides "${BRANCH_LIMIT_OVERRIDES}" \
  --coal-capacity-scale ${COAL_CAPACITY_SCALE} \
  --gas-capacity-scale ${GAS_CAPACITY_SCALE} \
  --capacity-rounding-mw ${CAPACITY_ROUNDING_MW} \
  --kernel-num ${KERNEL_NUM} \
  --samples-per-kernel ${SAMPLES_PER_KERNEL} \
  --seed ${SEED} \
  --smoke-hours ${SMOKE_HOURS}
