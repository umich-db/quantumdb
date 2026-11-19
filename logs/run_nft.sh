#!/bin/bash
# QAOA from an existing single-start SPIQ point (new formulation) + postprocess.
# Usage: run_nft.sh <input_idx> <week> <spiq_week> [optimizer=3 (NFT) | 1 (COBYLA)] [evaluations=1000]
# Logs to logs/nft_<week>_input<idx>.log (named for its first use; the optimizer is an argument).
set -e
IDX="$1"; WEEK="$2"; SPIQ_WEEK="$3"; OPT_ID="${4:-3}"; ITER="${5:-1000}"
case "${OPT_ID}" in 1) OPT=COBYLA ;; 3) OPT=NFT ;; *) echo "optimizer must be 1 or 3"; exit 1 ;; esac
REPO=/home/repro/sigmod-repro
JSON=$(ls "${REPO}/spiq_init_outputs/single_${SPIQ_WEEK}"/spiq_initial_point_input"${IDX}"_reps2_*_qaoa.json)
echo "=== start $(date): ${OPT}, ${ITER} evaluations, ${JSON}"
cd "${REPO}/base"
python3 IBMQExperiments.py --trial 1 --reps 2 --optimizer "${OPT_ID}" --iterations "${ITER}" --input_idx "${IDX}" \
  --week "${WEEK}" --spiq_json "${JSON}" --spiq_starts 1
PCIRC="${REPO}/base/${WEEK}/ExperimentalAnalysis/IBMQ/QPUPerformance/Results/CPU_Data/iterations_${ITER}/reps_2/${OPT}/input${IDX}/trial1/pcirc.qpy"
[ -f "${PCIRC}" ] || { echo "=== FAILED: ${PCIRC} missing, QAOA did not run from SPIQ $(date)"; exit 1; }
echo "=== qaoa done $(date)"
cd "${REPO}"
python3 base/postprocess_results.py --trial 1 --reps 2 --optimizer "${OPT}" --input_idx "${IDX}" --iterations "${ITER}" --week "${WEEK}"
cd "${REPO}/base"
mv "ExperimentalAnalysis/IBMQ/QPUPerformance/Results/CPU_Data/${ITER}_Iterations/${IDX}_predicates-newQUBO/trial1" "${WEEK}/response_pickle_trial1_qaoa"
echo "=== all done $(date)"
