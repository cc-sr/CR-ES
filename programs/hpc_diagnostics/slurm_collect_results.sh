#!/bin/bash
#SBATCH --job-name=collect_shap
#SBATCH --output=slurm-%x-%A.out
#SBATCH --error=slurm-%x-%A.err
#SBATCH --time=00:30:00
#SBATCH --partition=64c512g
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2

HPC_HOME=${HPC_HOME:-$HOME}
if [[ -f "${HPC_HOME}/.bashrc" ]]; then
  source "${HPC_HOME}/.bashrc"
fi
CONDA_ENV=${CONDA_ENV:-cr-es}
conda activate ${CONDA_ENV}

export PATH=$(conda info --base)/envs/${CONDA_ENV}/bin:$PATH
export LD_LIBRARY_PATH=$(conda info --base)/envs/${CONDA_ENV}/lib:${LD_LIBRARY_PATH:-}
export MOSEKLM_LICENSE_FILE=${MOSEKLM_LICENSE_FILE:-${HPC_HOME}/mosek.lic}

PROJECT_DIR=${PROJECT_DIR:-$(cd "$(dirname "$0")" && pwd)}
CASE_TAG=${CASE_TAG:-ES130_110MW}
EXPECTED_PERIODS=${EXPECTED_PERIODS:-72}

python ${PROJECT_DIR}/collect_kernel_results.py \
  --case-tag ${CASE_TAG} \
  --expected-periods ${EXPECTED_PERIODS}
