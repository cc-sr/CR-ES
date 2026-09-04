#!/bin/bash
#SBATCH --job-name=i118_kernel
#SBATCH --output=slurm-%x-%A_%a.out
#SBATCH --error=slurm-%x-%A_%a.err
#SBATCH --time=24:00:00
#SBATCH --partition=64c512g
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=500G
#SBATCH --array=0-23
#SBATCH --cpus-per-task=1

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
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

PROJECT_DIR=${PROJECT_DIR:-$(cd "$(dirname "$0")" && pwd)}
CASE_TAG=${CASE_TAG:-PT118_ADJ_coal45_gas20_res300_one_local_fixedthermal_4h}
KERNEL_NUM=${KERNEL_NUM:-5000}
SAMPLES_PER_KERNEL=${SAMPLES_PER_KERNEL:-100}
CHECKPOINT_EVERY=${CHECKPOINT_EVERY:-5}

python ${PROJECT_DIR}/run_kernel_period.py \
  --case-tag ${CASE_TAG} \
  --period ${SLURM_ARRAY_TASK_ID} \
  --kernel-num ${KERNEL_NUM} \
  --samples-per-kernel ${SAMPLES_PER_KERNEL} \
  --checkpoint-every ${CHECKPOINT_EVERY} \
  --workers ${SLURM_CPUS_PER_TASK}
