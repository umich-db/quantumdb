#!/bin/bash
# Run SPIQ-initialized QAOA (COBYLA, reps=2) for 3 trials on one paper problem.
# Requires the SPIQ JSON produced beforehand by base/spiq_initialization.py.
# Drop --spiq_json to run the random-initialization baseline instead.

cd /home/repro/sigmod-repro/base

# Problem folder <idx>_predicates: 0=P1, 1=P2, 2=P3.
SPIQ_INPUT_IDX=${1:-0}
SPIQ_DIR=/home/repro/sigmod-repro/spiq_init_outputs

echo "Started running IBMQ experiments..."

for opt in 1; do          # 1 = COBYLA
  for reps in 2; do
    spiq_json="${SPIQ_DIR}/spiq_initial_point_input${SPIQ_INPUT_IDX}_reps${reps}.json"
    if [ ! -f "${spiq_json}" ]; then
      echo "SPIQ init file missing: ${spiq_json}" >&2
      echo "Regenerate with: python3 spiq_initialization.py --input_idx ${SPIQ_INPUT_IDX} --reps ${reps} --n_gens 200" >&2
      exit 1
    fi

    for trial in 1 2 3; do
      echo "Running trial=${trial}, reps=${reps}, optimizer=${opt}, spiq_json=${spiq_json}"
      python3 IBMQExperiments.py \
        --trial "${trial}" \
        --reps "${reps}" \
        --optimizer "${opt}" \
        --spiq_json "${spiq_json}" \
        --input_idx "${SPIQ_INPUT_IDX}" \
        >> "ibmq_experiment_opt${opt}_reps${reps}_trial${trial}.log" 2>&1
    done
  done
done

echo "IBMQ experiments done."
