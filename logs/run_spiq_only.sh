#!/bin/bash
# Single-start SPIQ only (no QAOA) + stim sampling of the starting point. Formulation from QUBO_FORMULATION.
# Usage: run_spiq_only.sh <input_idx> <week> <opt_cost>   (logs to logs/spiqonly_<week>_input<idx>.log)
set -e
IDX="$1"; WEEK="$2"; OPT="$3"
REPO=/home/repro/sigmod-repro
OUT="${REPO}/spiq_init_outputs/single_${WEEK}"
echo "=== start $(date) formulation=${QUBO_FORMULATION}"
cd "${REPO}/base"
export PYTHONPATH="/home/repro/spiq-site:${PYTHONPATH}"
python3 spiq_initialization.py --input_idx "${IDX}" --reps 2 --n_gens 2000 --n_starts 1 --n_proc 8 --seed 0 \
  --energy_window 0.25 --n_candidates 1 --out_dir "${OUT}"
JSON=$(ls "${OUT}"/spiq_initial_point_input"${IDX}"_reps2_*_"${QUBO_FORMULATION}".json)
echo "=== spiq done $(date): ${JSON}"
python3 spiq_sample.py --json "${JSON}" --opt_cost "${OPT}"
echo "=== all done $(date)"
