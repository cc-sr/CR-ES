#!/bin/bash
#SBATCH --job-name=collect_shap
#SBATCH --output=/dssg/home/acct-seed/chensiru/carbon/es/output/collect_shap_%A.out
#SBATCH --error=/dssg/home/acct-seed/chensiru/carbon/es/output/collect_shap_%A.err
#SBATCH --time=00:30:00
#SBATCH --partition=64c512g
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2

source /dssg/home/acct-seed/chensiru/.bashrc
conda activate trialenv

export PATH=$(conda info --base)/envs/trialenv/bin:$PATH
export LD_LIBRARY_PATH=$(conda info --base)/envs/trialenv/lib:$LD_LIBRARY_PATH
export MOSEKLM_LICENSE_FILE=/dssg/home/acct-seed/chensiru/mosek.lic

PROJECT_DIR=${PROJECT_DIR:-$(cd "$(dirname "$0")" && pwd)}
CASE_TAG=${CASE_TAG:-ES130_110MW}
EXPECTED_PERIODS=${EXPECTED_PERIODS:-72}

mkdir -p /dssg/home/acct-seed/chensiru/carbon/es/output

python ${PROJECT_DIR}/collect_kernel_results.py \
  --case-tag ${CASE_TAG} \
  --expected-periods ${EXPECTED_PERIODS}
