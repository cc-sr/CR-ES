#!/bin/bash
#SBATCH --job-name=kernel_shap
#SBATCH --output=slurm-%x-%A_%a.out
#SBATCH --error=slurm-%x-%A_%a.err
#SBATCH --time=04:00:00
#SBATCH --partition=64c512g
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-71
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
CASE_TAG=${CASE_TAG:-ES130_110MW}
KERNEL_NUM=${KERNEL_NUM:-1000}
SAMPLES_PER_KERNEL=${SAMPLES_PER_KERNEL:-100}
CHECKPOINT_EVERY=${CHECKPOINT_EVERY:-5}

python ${PROJECT_DIR}/run_kernel_period.py \
  --case-tag ${CASE_TAG} \
  --period ${SLURM_ARRAY_TASK_ID} \
  --kernel-num ${KERNEL_NUM} \
  --samples-per-kernel ${SAMPLES_PER_KERNEL} \
  --checkpoint-every ${CHECKPOINT_EVERY} \
  --workers ${SLURM_CPUS_PER_TASK}
