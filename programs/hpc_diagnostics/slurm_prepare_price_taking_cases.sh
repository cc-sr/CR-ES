#!/bin/bash
#SBATCH --job-name=prep_i14_pt
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

PROJECT_DIR=${PROJECT_DIR:-$(cd "$(dirname "$0")" && pwd)}
KERNEL_NUM=${KERNEL_NUM:-1000}
SAMPLES_PER_KERNEL=${SAMPLES_PER_KERNEL:-100}
SEED=${SEED:-1126}
SMOKE_HOURS=${SMOKE_HOURS:-24}
CASE_GROUP=${CASE_GROUP:-location}
CASE_TAGS=${CASE_TAGS:-}

if [[ -n "${CASE_TAGS}" ]]; then
  python ${PROJECT_DIR}/prepare_ieee14_location_cases_24h.py \
    --cases ${CASE_TAGS} \
    --kernel-num ${KERNEL_NUM} \
    --samples-per-kernel ${SAMPLES_PER_KERNEL} \
    --seed ${SEED} \
    --smoke-hours ${SMOKE_HOURS}
else
  python ${PROJECT_DIR}/prepare_ieee14_location_cases_24h.py \
    --case-group ${CASE_GROUP} \
    --kernel-num ${KERNEL_NUM} \
    --samples-per-kernel ${SAMPLES_PER_KERNEL} \
    --seed ${SEED} \
    --smoke-hours ${SMOKE_HOURS}
fi
