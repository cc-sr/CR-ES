#!/bin/bash
#SBATCH --job-name=prep_shapley
#SBATCH --output=/dssg/home/acct-seed/chensiru/carbon/es/output/prep_shapley_%A.out
#SBATCH --error=/dssg/home/acct-seed/chensiru/carbon/es/output/prep_shapley_%A.err
#SBATCH --time=00:30:00
#SBATCH --partition=64c512g
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2

source /dssg/home/acct-seed/chensiru/.bashrc
CONDA_ENV=${CONDA_ENV:-cr-es}
conda activate ${CONDA_ENV}

export PATH=$(conda info --base)/envs/${CONDA_ENV}/bin:$PATH
export LD_LIBRARY_PATH=$(conda info --base)/envs/${CONDA_ENV}/lib:$LD_LIBRARY_PATH
export MOSEKLM_LICENSE_FILE=/dssg/home/acct-seed/chensiru/mosek.lic
export MOSEK_NUM_THREADS=1

PROJECT_DIR=${PROJECT_DIR:-$(cd "$(dirname "$0")" && pwd)}
CASE_TAG=${CASE_TAG:-ES130_110MW}
EXPERIMENT=${EXPERIMENT:-storage}
DAYS=${DAYS:-3}
DURATION_H=${DURATION_H:-4}
KERNEL_NUM=${KERNEL_NUM:-1000}
SAMPLES_PER_KERNEL=${SAMPLES_PER_KERNEL:-100}
NETWORK_CAPACITY_SCALE=${NETWORK_CAPACITY_SCALE:-2.0}

mkdir -p /dssg/home/acct-seed/chensiru/carbon/es/output

python ${PROJECT_DIR}/prepare_shapley_cases.py \
  --experiment ${EXPERIMENT} \
  --scenario ${CASE_TAG} \
  --duration-h ${DURATION_H} \
  --days ${DAYS} \
  --max-kernel-num ${KERNEL_NUM} \
  --samples-per-kernel ${SAMPLES_PER_KERNEL} \
  --seed 1126 \
  --network-capacity-scale ${NETWORK_CAPACITY_SCALE}
