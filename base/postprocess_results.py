"""Turn IBMQExperiments.py outputs into join-order readouts (paper §3.3, §5).

For each trial it
  1. re-simulates the QAOA state at selected optimizer evaluations (default:
     eval 1, the first iteration) from energy_per_iteration_*.csv and writes
     readout_summary_eval<k>.csv,
  2. decodes the pickled final response into readout_summary.csv,
  3. prints the exact ground-state energy of the QUBO (the dashed line in Figs. 3–5).
The readout CSVs carry both the raw and the fallback join order per bitstring;
visualization.rmd computes the cost ratio / optimal ratio (Table 1) from them.

Run from the repository root (paths are prefixed with base/):
    python3 base/postprocess_results.py --trial 1 2 3 --reps 2 --week Week84
"""

import argparse
import csv
import os
import pickle
import re

import numpy as np
from qiskit.algorithms import NumPyMinimumEigensolver
from qiskit.circuit.library.n_local.qaoa_ansatz import QAOAAnsatz
from qiskit.providers.aer import QasmSimulator
from qiskit.utils import QuantumInstance

import Scripts.Postprocessing as Postprocessing
import Scripts.ProblemGenerator as ProblemGenerator
import Scripts.QUBOGenerator as QUBOGenerator


def load_pickled_result(path_string):
    """Load the response pickled by IBMQExperiments.pickle_results."""
    with open(os.path.abspath(path_string + '/results.txt'), 'rb') as file:
        return pickle.load(file)


def run_callback_parameter_simulation_and_postprocess(
    parameters,
    qubo,
    reps,
    card,
    pred,
    pred_sel,
    card_dict=None,
    quantum_instance=None,
    shots=10240,
    opt_time_ms=0.0,
    base_dir="./Week4/ExperimentalAnalysis/IBMQ/QPUPerformance/Results/CPU_Data",
    trial_id=1,
    tag=4,
    current_optim="COBYLA",
    iterations=10000,
    input_id=0,
    eval_count=None
):
    """Bind `parameters` into the vanilla QAOAAnsatz, sample it and write its readout CSV.

    Note: parameters are bound positionally into the 2*reps-angle QAOAAnsatz.
    For SPIQ runs the logged parameters are per-gate angles of the relaxed
    pcirc, so only the first 2*reps of them are used here.
    """
    if card_dict is None:
        card_dict = {}

    if quantum_instance is None:
        quantum_instance = QuantumInstance(backend=QasmSimulator(), shots=shots)

    op, _ = qubo.to_ising()

    ansatz = QAOAAnsatz(op, reps=reps).decompose()
    param_map = {p: v for p, v in zip(ansatz.parameters, parameters)}

    qc = ansatz.assign_parameters(param_map, inplace=False)
    qc.measure_all()

    execute_result = quantum_instance.execute(qc)

    best_for_time, all_solutions, solutions_for_readout = postprocess_callback_execute_with_readout(
        execute_result=execute_result,
        qubo=qubo,
        card=card,
        pred=pred,
        pred_sel=pred_sel,
        card_dict=card_dict,
        opt_time_ms=opt_time_ms,
        base_dir=base_dir,
        trial_id=trial_id,
        tag=tag,
        current_optim=current_optim,
        iterations=iterations,
        input_id=input_id,
        eval_count=eval_count
    )

    return {
        "execute_result": execute_result,
        "best_for_time": best_for_time,
        "all_solutions": all_solutions,
        "solutions_for_readout": solutions_for_readout,
    }


def batch_run_callback_history_and_postprocess(callback_history, **kwargs):
    """Run `run_callback_parameter_simulation_and_postprocess` for every entry of a callback history."""
    results = []
    for item in callback_history:
        eval_count = int(item["eval_count"])
        one_result = run_callback_parameter_simulation_and_postprocess(
            parameters=item["parameters"], eval_count=eval_count, **kwargs)
        results.append({
            "eval_count": eval_count,
            "parameters": item["parameters"],
            "best_for_time": one_result["best_for_time"],
            "all_solutions": one_result["all_solutions"],
            "solutions_for_readout": one_result["solutions_for_readout"],
        })
    return results


def postprocess_callback_execute_with_readout(
    execute_result,
    qubo,
    card,
    pred,
    pred_sel,
    card_dict=None,
    opt_time_ms=0.0,
    base_dir="./Week4/ExperimentalAnalysis/IBMQ/QPUPerformance/Results/CPU_Data",
    trial_id=1,
    tag=4,
    current_optim="COBYLA",
    iterations=10000,
    input_id=0,
    eval_count=None
):
    """Decode the counts of `execute_result` into join orders and write readout_summary[_eval<k>].csv."""
    if card_dict is None:
        card_dict = {}

    result_dir = os.path.join(
        base_dir,
        f"iterations_{iterations}",
        f"reps_{tag}",
        f"{current_optim}",
        f"input{input_id}",
        f"trial{trial_id}"
    )

    os.makedirs(result_dir, exist_ok=True)
    print("Save to " + result_dir)

    suffix = f"_eval{eval_count}" if eval_count is not None else ""
    csv_path = os.path.join(result_dir, f"readout_summary{suffix}.csv")

    counts = execute_result.get_counts()

    if not counts:
        raise ValueError("execute_result.get_counts() empty")

    total = sum(counts.values())
    solutions = []

    # Most frequent bitstrings first; reverse qiskit's MSB-first order into QUBO variable order.
    for bitstring, cnt in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
        x = [int(ch) for ch in bitstring.replace(" ", "")[::-1]]
        energy = float(qubo.objective.evaluate(x))
        solutions.append([x, int(cnt), energy, "".join(map(str, x)), cnt / total])

    best_for_time, all_solutions = Postprocessing.readout(
        [solutions, float(opt_time_ms)], card, pred, pred_sel, card_dict)
    Postprocessing.write_readout_csv(csv_path, best_for_time, all_solutions)

    print(f"Saved to {csv_path}")

    return best_for_time, all_solutions, solutions


def _parse_parameter_string(param_str):
    """
    Parse the 'paramter' column from energy_per_iteration_*.csv.

    The CSV is written by csv.writer.writerow((.., list(theta), ..)),
    which stringifies the parameter list as '[1.57, 4.71, 3.14]'.
    This accepts both comma-separated and whitespace-separated formats.
    """
    s = param_str.strip()

    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]

    parts = [p for p in re.split(r"[,\s]+", s.strip()) if p]

    return [float(x) for x in parts]


def convert_callback_csv_to_history(csv_path, encoding="utf-8"):
    """Read energy_per_iteration_*.csv into [{eval_count, parameters, callback_value, stddev}, ...]."""
    callback_history = []

    with open(csv_path, "r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            param_col = "paramter" if "paramter" in row else "parameter"

            try:
                stddev_val = float(row.get("std", ""))
            except (TypeError, ValueError):
                stddev_val = 0.0

            callback_history.append({
                "eval_count": int(row["iteration"]),
                "parameters": _parse_parameter_string(row[param_col]),
                "callback_value": float(row["energy"]),
                "stddev": stddev_val,
            })

    return callback_history


def print_ground_state_energy(qubo):
    """Exact minimum eigenvalue of the Ising Hamiltonian, printed in Ising and QUBO scale."""
    op, offset = qubo.to_ising()
    print(f"ising Hamiltonian is: {op}; with offset of {offset}")
    result = NumPyMinimumEigensolver().compute_minimum_eigenvalue(op)
    print("minimum eigenvalue:", result.eigenvalue)
    print("minimum eigenstate:", result.eigenstate)
    print("minimum energy with offset:", result.eigenvalue.real + offset)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--trial", type=int, nargs="+", default=[1], help="Trial ids to process")
    parser.add_argument("--reps", type=int, default=2, help="QAOA depth p")
    parser.add_argument("--optimizer", default="COBYLA", help="Optimizer name used in result paths")
    parser.add_argument("--input_idx", type=int, default=0, help="Problem folder index (<idx>_predicates)")
    parser.add_argument("--iterations", type=int, default=10000, help="Iterations value used in result paths")
    parser.add_argument("--week", default="Week4", help="Results directory passed to IBMQExperiments.py --week")
    parser.add_argument("--evals", type=int, nargs="+", default=[1], help="Optimizer evaluations to re-simulate")
    args = parser.parse_args()

    input_id, reps, current_optim, iterations = args.input_idx, args.reps, args.optimizer, args.iterations
    result_path_prefix = 'base/ExperimentalAnalysis/IBMQ/QPUPerformance/Results/CPU_Data/'
    base_dir = f"./{args.week}/ExperimentalAnalysis/IBMQ/QPUPerformance/Results/CPU_Data"

    card, pred, pred_sel = ProblemGenerator.get_join_ordering_problem(
        'base/ExperimentalAnalysis/IBMQ/QPUPerformance/Problems/JSON/' + str(input_id) + '_predicates')
    qubo, penalty_weight = QUBOGenerator.generate_IBMQ_QUBO_for_left_deep_trees_v2(card, pred, pred_sel)

    for trial in args.trial:
        response = load_pickled_result(
            f"{result_path_prefix}/{iterations}_Iterations/{input_id}_predicates-newQUBO/trial{trial}")

        energy_csv_path = (
            f'base/{args.week}/ExperimentalAnalysis/IBMQ/QPUPerformance/Results/CPU_Data/'
            f'iterations_{iterations}/reps_{reps}/{current_optim}/input{input_id}/trial{trial}/'
            f'energy_per_iteration_{iterations}_{current_optim}_{reps}_{trial}.csv'
        )

        # eval_count 1 = first optimizer evaluation (the initial state for SPIQ runs).
        res_filtered = [item for item in convert_callback_csv_to_history(energy_csv_path)
                        if int(item["eval_count"]) in args.evals]

        if not res_filtered:
            print(f"[WARNING] None of eval counts {args.evals} found in {energy_csv_path}.")
        else:
            print(f"Generating readout summaries for eval counts: {sorted({int(i['eval_count']) for i in res_filtered})}")

        batch_run_callback_history_and_postprocess(
            res_filtered,
            qubo=qubo,
            card=card,
            pred=pred,
            pred_sel=pred_sel,
            reps=reps,
            base_dir=base_dir,
            trial_id=trial,
            tag=reps,
            current_optim=current_optim,
            iterations=iterations,
            input_id=input_id
        )

        Postprocessing.postprocess_qiskit_with_readout(
            response, card, pred, pred_sel,
            trial_id=trial, tag=reps, current_optim=current_optim,
            iterations=iterations, base_dir=base_dir,
        )

        print_ground_state_energy(qubo)


if __name__ == '__main__':
    main()
