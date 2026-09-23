"""QAOA driver for join order optimization (paper §3–§5).

Builds the join-ordering QUBO (Scripts/QUBOGenerator.py), then minimises it
with QAOA in one of two modes:

* Random / uninformed initialization (no --spiq_json): stock qiskit `QAOA`
  over the 2*reps angles (gamma, beta), started from a fixed point.
* SPIQ initialization (--spiq_json <file>): loads the relaxed per-gate
  circuit `pcirc` and the Clifford initial point written by
  spiq_initialization.py, and optimises every per-gate angle directly.

Both modes log the energy of every optimizer evaluation (QUBO scale, i.e.
directly comparable with qubo.objective.evaluate(x)) to
energy_per_iteration_*.csv (paper Figs. 3–5), then re-sample the best
parameters seen and store the samples as min_state_readout.csv plus a pickled
response that postprocess_results.py decodes into join orders (Table 1).

Usage (from base/):
    python3 IBMQExperiments.py --trial 1 --reps 2 --optimizer 1 [--spiq_json <json>] [--week Week84]
"""

import argparse
import csv
import json
import os
import pathlib
import pickle
import sys
from types import SimpleNamespace

import numpy as np
from qiskit import IBMQ
from qiskit.algorithms import QAOA
from qiskit.algorithms.optimizers import AQGD, COBYLA, SPSA
from qiskit.circuit.library.n_local.qaoa_ansatz import QAOAAnsatz
from qiskit.providers.aer import QasmSimulator
from qiskit.utils import QuantumInstance
from qiskit_optimization.algorithms import MinimumEigenOptimizer

try:
    from qiskit import qpy
except ImportError:  # older qiskit releases
    from qiskit.circuit import qpy_serialization as qpy

import config
import Scripts.Postprocessing as Postprocessing
import Scripts.ProblemGenerator as ProblemGenerator
import Scripts.QUBOGenerator as QUBOGenerator

parser = argparse.ArgumentParser()
parser.add_argument("--trial", type=int, default=1, help="Trial number, used in result paths")
parser.add_argument("--reps", type=int, default=1, help="QAOA depth p")
parser.add_argument("--optimizer", type=int, default=0, help="0=AQGD, 1=COBYLA (used in the paper), 2=SPSA")
parser.add_argument(
    "--spiq_json",
    type=str,
    default=None,
    help=(
        "Path to SPIQ initialization JSON produced by spiq_initialization.py. "
        "If provided, run the optimizer over the relaxed ansatz (per-gate angles) "
        "instead of the vanilla QAOAAnsatz."
    ),
)
parser.add_argument("--week", type=str, default="Week84", help="Top-level results directory (relative to base/)")
parser.add_argument("--iterations", type=int, default=10000, help="Optimizer max iterations")
parser.add_argument("--input_idx", type=int, default=0, help="Problem folder <idx>_predicates: 0=P1, 1=P2, 2=P3")
args, _ = parser.parse_known_args()

TRIAL_ID = args.trial
TAG = args.reps
optmi = args.optimizer
SPIQ_JSON = args.spiq_json
current_optim = {0: "AQGD", 1: "COBYLA"}.get(optmi, "SPSA")

SHOTS = 10240  # shots for every sampled readout


def pickle_results(path_string, results):
    """Pickle `results` to <path_string>/results.txt."""
    pathlib.Path(os.path.abspath(path_string)).mkdir(parents=True, exist_ok=True)
    datafile = os.path.abspath(path_string + '/results.txt')
    print("Saving " + path_string)
    with open(datafile, 'wb') as file:
        pickle.dump(results, file)


def get_local_QASM_backend():
    """Local noiseless simulator used for all paper experiments."""
    return QuantumInstance(backend=QasmSimulator(), shots=SHOTS)


def get_IBMQ_backend():
    """Real IBM Q backend configured in config.py (only for ibmq-processing = "qpu")."""
    provider = IBMQ.get_provider(hub=config.configuration["ibmq-hub"],
                                 group=config.configuration["ibmq-group"],
                                 project=config.configuration["ibmq-project"])
    backend = provider.get_backend(config.configuration["ibmq-backend"])
    return QuantumInstance(backend=backend)


def get_optimizer(iterations):
    """Classical optimizer selected by --optimizer (COBYLA settings are the ones used in the paper)."""
    if optmi == 1:
        return COBYLA(maxiter=iterations, rhobeg=2.0, tol=1e-12, disp=True)
    if optmi == 2:
        return SPSA(maxiter=iterations)
    return AQGD(maxiter=iterations, eta=0.01)


def _make_spiq_sample(x, fval, probability):
    """Return a pickle-safe sample object shaped like qiskit_optimization
    samples (.x / .fval / .probability). Using SimpleNamespace avoids the
    `Can't get attribute '_SpiqResponse' on <module '__main__'>` failure
    that custom classes produce when the pickle is loaded from a different
    entrypoint (e.g. postprocess_results.py) than the one that wrote it."""
    return SimpleNamespace(x=x, fval=fval, probability=probability)


def _make_spiq_response(x, fval, samples):
    """Pickle-safe response shaped like MinimumEigenOptimizer.solve()'s
    result (.x / .fval / .samples)."""
    return SimpleNamespace(x=x, fval=fval, samples=samples)


def _load_spiq_initialization(json_path):
    """
    Load the JSON + QPY artifacts produced by spiq_initialization.py.
    Returns (pcirc, relaxed_initial_point, spiq_meta).

    The `pcirc_qpy` field in the JSON may be a relative path. We resolve
    it in this order:
      1. As-is (works if the caller's cwd matches where SPIQ was run).
      2. Next to the JSON file (by basename).
      3. Relative to the JSON file's own directory.
      4. Relative to the JSON file's parent directory (covers
         cwd = base/ launching a JSON that lives at the repo root).
    """
    json_path = os.path.abspath(json_path)
    with open(json_path, "r") as f:
        meta = json.load(f)

    raw_qpy = meta["pcirc_qpy"]
    json_dir = os.path.dirname(json_path)
    candidates = [
        raw_qpy,
        os.path.join(json_dir, os.path.basename(raw_qpy)),
        os.path.join(json_dir, raw_qpy),
        os.path.join(os.path.dirname(json_dir), raw_qpy),
    ]
    qpy_path = next((p for p in candidates if os.path.exists(p)), None)
    if qpy_path is None:
        raise FileNotFoundError(
            f"Could not locate pcirc QPY (declared as {raw_qpy!r} in {json_path}). "
            f"Tried: {candidates}"
        )

    with open(qpy_path, "rb") as f:
        pcirc = qpy.load(f)[0]
    return pcirc, list(meta["relaxed_initial_point"]), meta


def _counts_to_samples(counts, qubo):
    """Convert measurement counts into sample dicts {x, fval, probability, count}.

    Qiskit bitstrings are MSB-first (qubit 0 is the rightmost character) and may
    contain register spaces; reversing yields x in QUBO variable order.
    `fval` is the QUBO objective of x.
    """
    shots = sum(counts.values())
    samples = []
    for bitstring, cnt in counts.items():
        x = [int(ch) for ch in bitstring.replace(" ", "")[::-1]]
        samples.append({"x": x, "fval": float(qubo.objective.evaluate(x)),
                        "probability": cnt / shots if shots else 0.0, "count": cnt})
    return samples


def _evaluate_expected_qubo_energy(counts, qubo):
    """Diagonal cost Hamiltonian: <H_C> = sum_x p(x) * qubo.objective.evaluate(x) (QUBO scale)."""
    return sum(s["probability"] * s["fval"] for s in _counts_to_samples(counts, qubo))


def _sample_min_state(qc, qubo, min_energy_seen, min_eval_idx, min_params):
    """Re-measure the best-seen parameters (already bound in `qc`) and describe that state."""
    counts = get_local_QASM_backend().execute(qc).get_counts()
    samples = _counts_to_samples(counts, qubo)
    return {
        "min_energy": float(min_energy_seen),
        "min_eval_idx": min_eval_idx,
        "min_params": min_params,
        "shots": sum(counts.values()),
        "samples": samples,
    }


def _write_energy_log(path, energies):
    """Write one row per optimizer evaluation: (iteration, QUBO-scale energy, parameters, std).

    The 'paramter' header typo is kept on purpose: downstream parsers and plots read it.
    """
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["iteration", "energy", "paramter", "std"])
        writer.writerows(energies)


def solve_with_QAOA_spiq(
    qubo,
    iterations,
    pcirc,
    relaxed_initial_point,
    result_dir,
    use_local_simulator=False,
    expected_energy=None,
    sanity_check_tolerance=0.25,
):
    """
    SPIQ-initialized QAOA: optimise over the RELAXED ansatz (one parameter
    per gate, as produced by SPIQ), starting from SPIQ's Clifford point and
    minimising the sampled diagonal QUBO cost.

    If `expected_energy` (SPIQ's Ising-scale energy_best) is given, first
    checks that binding the initial point into pcirc reproduces it.

    Returns (response, final_point, used_eval, min_state_buffer), the same
    shape as `solve_with_QAOA`.
    """
    quantum_instance = get_local_QASM_backend() if use_local_simulator else get_IBMQ_backend()

    os.makedirs(result_dir, exist_ok=True)
    energy_log_path = os.path.join(
        result_dir,
        f"energy_per_iteration_{iterations}_{current_optim}_{TAG}_{TRIAL_ID}.csv",
    )

    energies = []
    min_energy_seen = float("inf")
    min_params = None
    min_eval_idx = None
    last_params = None
    eval_count = 0

    ordered_params = list(pcirc.parameters)
    n_params = len(ordered_params)
    if len(relaxed_initial_point) != n_params:
        raise ValueError(
            f"relaxed_initial_point length ({len(relaxed_initial_point)}) "
            f"does not match pcirc.parameters length ({n_params})."
        )

    measured_circ = pcirc.copy()
    measured_circ.measure_all()

    def _bind(theta_vec):
        return measured_circ.assign_parameters(
            {p: float(v) for p, v in zip(ordered_params, theta_vec)},
            inplace=False,
        )

    def evaluate_qubo_energy_only(theta_vec):
        counts = quantum_instance.execute(_bind(theta_vec)).get_counts()
        return _evaluate_expected_qubo_energy(counts, qubo)

    def cost_fn(theta_vec):
        """Optimizer objective; also logs every evaluation and tracks the best one."""
        nonlocal min_energy_seen, min_params, min_eval_idx, last_params, eval_count
        energy = evaluate_qubo_energy_only(theta_vec)

        eval_count += 1
        last_params = list(theta_vec)
        # 4th column mirrors vanilla QAOA's 'std' column. We don't compute
        # one for the custom cost_fn (it's a deterministic scalar), so emit
        # 0.0 to keep the CSV schema uniform with downstream parsers like
        # postprocess_results.convert_callback_csv_to_history.
        energies.append((eval_count, energy, list(theta_vec), 0.0))

        if energy < min_energy_seen:
            min_energy_seen = energy
            min_params = list(theta_vec)
            min_eval_idx = eval_count
        return energy

    if expected_energy is not None:
        # SPIQ's energy_best is the Ising-basis expectation (no offset).
        # Our simulator evaluates qubo.objective on sampled bitstrings, which
        # is in the QUBO basis. The two differ exactly by the offset returned
        # by qubo.to_ising(), so subtract it before comparing.
        _op, ising_offset = qubo.to_ising()
        sanity_counts = get_local_QASM_backend().execute(_bind(relaxed_initial_point)).get_counts()
        sanity_energy_qubo = _evaluate_expected_qubo_energy(sanity_counts, qubo)
        sanity_energy_ising = sanity_energy_qubo - float(ising_offset)
        rel_err = abs(sanity_energy_ising - expected_energy) / max(abs(expected_energy), 1e-9)
        print(
            f"[spiq-sanity] expected_energy (from SPIQ, Ising) = {expected_energy:.6f}, "
            f"simulator <H_C>_QUBO at relaxed_initial_point = {sanity_energy_qubo:.6f}, "
            f"simulator <H_C>_Ising (= QUBO - offset {ising_offset:.4f}) = {sanity_energy_ising:.6f}, "
            f"rel_err = {rel_err:.3f}"
        )
        if rel_err > sanity_check_tolerance:
            raise RuntimeError(
                f"Sanity check failed: simulator Ising energy {sanity_energy_ising:.6f} diverges "
                f"from SPIQ reported {expected_energy:.6f} (relative error {rel_err:.3f} > "
                f"tolerance {sanity_check_tolerance}). This usually means the relaxed "
                "pcirc is not being bound to the same Clifford state as stim. "
                "Common causes: dropped sign on the gate multiplier when computing "
                "`relaxed_initial_point`, bitstring endianness mismatch in "
                "`_counts_to_samples`, or a stale QPY file."
            )

    # Let the optimizer start from the SPIQ point.
    opt_result = get_optimizer(iterations).minimize(fun=cost_fn, x0=np.asarray(relaxed_initial_point))

    # Diagnostic only: energy at the SPIQ point, re-sampled after optimisation.
    initial_energy = evaluate_qubo_energy_only(np.asarray(relaxed_initial_point))
    print(f"[spiq-init] logged iteration 0 energy = {initial_energy}")

    _write_energy_log(energy_log_path, energies)

    final_point = last_params if last_params is not None else list(relaxed_initial_point)

    min_state_buffer = None
    samples = []
    if min_params is not None:
        try:
            min_state_buffer = _sample_min_state(_bind(min_params), qubo, min_energy_seen, min_eval_idx, min_params)
            samples = min_state_buffer["samples"]
        except Exception as exc:
            print(f"[spiq-solver] sampling best-seen params failed: {exc}")

    best = min(samples, key=lambda s: s["fval"], default=None)
    response = _make_spiq_response(
        x=best["x"] if best else [0] * n_params,
        fval=best["fval"] if best else float(opt_result.fun),
        samples=[_make_spiq_sample(s["x"], s["fval"], s["probability"]) for s in samples],
    )

    print(
        f"[spiq-solver] done: n_params={n_params}, "
        f"used_eval={eval_count}, best_energy={min_energy_seen}, "
        f"opt_result.fun={opt_result.fun}"
    )

    return response, final_point, eval_count, min_state_buffer


def solve_with_QAOA(qubo, iterations, result_dir, reps=TAG, use_local_simulator=False):
    """
    Randomly/uninformed-initialized QAOA baseline: stock qiskit QAOA over the
    2*reps angles, started from a fixed point.

    Returns (qaoa_result, final_point, used_eval, min_state_buffer) where
    min_state_buffer holds samples of the minimum-energy parameters seen.
    """
    quantum_instance = get_local_QASM_backend() if use_local_simulator else get_IBMQ_backend()

    os.makedirs(result_dir, exist_ok=True)
    energy_log_path = os.path.join(result_dir, f"energy_per_iteration_{iterations}_{current_optim}_{TAG}_{TRIAL_ID}.csv")
    energies = []
    last_params = None
    last_eval = 0

    # Qiskit QAOA callback reports the Ising expectation value.
    # Samples/postprocessing use qubo.objective.evaluate(x), which is in the
    # original QUBO objective scale. Convert every callback energy to QUBO
    # scale by adding the Ising offset, so energy_per_iteration_*.csv is
    # directly comparable with energies of sampled bitstring distributions.
    op, ising_offset = qubo.to_ising()
    ising_offset = float(ising_offset)
    print(f"[energy-scale] vanilla QAOA callback energies will be logged as QUBO-scale: Ising mean + offset ({ising_offset})")

    # Track minimum QUBO-scale energy seen during optimization and the corresponding parameters
    min_energy_seen = float('inf')
    min_params = None
    min_eval_idx = None

    def callback(eval_count, parameters, mean, metadata):
        """Called by qiskit QAOA after every energy evaluation; `metadata` is the std estimate."""
        nonlocal min_energy_seen, min_params, min_eval_idx, last_params, last_eval
        energy_value = float(np.real(mean)) + ising_offset
        energies.append((eval_count, energy_value, parameters, metadata))
        last_params = list(parameters)
        last_eval = int(eval_count)
        if energy_value < min_energy_seen:
            min_energy_seen = energy_value
            min_params = list(parameters)
            min_eval_idx = int(eval_count)

    # Uninformed starting point used for the "Random Initialization" baseline.
    # ponytail: fixed 0.5 for every angle, not a random draw; seed a RNG if true random starts are needed.
    initial_point = [0.5] * (2 * reps)

    qaoa_meas = QAOA(optimizer=get_optimizer(iterations), quantum_instance=quantum_instance,
                     reps=reps, initial_point=initial_point, callback=callback)
    qaoa_result = MinimumEigenOptimizer(qaoa_meas).solve(qubo)

    _write_energy_log(energy_log_path, energies)

    final_point = last_params if last_params is not None else initial_point

    # Re-sample the minimum-energy state found (parameters + measured samples).
    min_state_buffer = None
    if min_params is not None:
        try:
            ansatz = QAOAAnsatz(op, reps)
            qc = ansatz.assign_parameters(dict(zip(ansatz.parameters, min_params)), inplace=False)
            qc.measure_all()
            min_state_buffer = _sample_min_state(qc, qubo, min_energy_seen, min_eval_idx, min_params)
        except Exception:
            min_state_buffer = None

    return qaoa_result, final_point, last_eval, min_state_buffer


def check_qubit_from_qubo_and_exit(qubo, max_qubits=23):
    """Exit early if the QUBO needs more qubits than we can simulate."""
    try:
        num_qubits = qubo.get_num_binary_vars()
    except Exception:
        num_qubits = len(qubo.variables)

    print(f"[INFO] qubit number = {num_qubits}", flush=True)

    if num_qubits > max_qubits:
        print(f"[STOP] qubit number {num_qubits} > {max_qubits}, terminate script.")
        sys.exit(0)

    return num_qubits


def conduct_IBMQ_QPU_experiments():
    """Run QAOA (SPIQ- or uninformed-initialized) on problem --input_idx and save all outputs."""
    processing = config.configuration["ibmq-processing"]
    if processing == "qpu":
        IBMQ.save_account(config.configuration["ibmq-token"])
        IBMQ.load_account()

    iterations = args.iterations
    for i in [args.input_idx]:
        card, pred, pred_sel = ProblemGenerator.get_join_ordering_problem('ExperimentalAnalysis/IBMQ/QPUPerformance/Problems/JSON/' + str(i) + '_predicates')

        print("Generating qubo", flush=True)
        qubo, penalty_weight = QUBOGenerator.generate_IBMQ_QUBO_for_left_deep_trees_v2(card, pred, pred_sel)
        check_qubit_from_qubo_and_exit(qubo, max_qubits=23)

        currentPath = f'{args.week}/ExperimentalAnalysis/IBMQ/QPUPerformance/Results/CPU_Data'
        result_dir = os.path.join(
            currentPath,
            f"iterations_{iterations}",
            f"reps_{TAG}",
            f"{current_optim}",
            f"input{i}",
            f"trial{TRIAL_ID}"
        )

        spiq_bundle = None
        if SPIQ_JSON:
            try:
                spiq_bundle = _load_spiq_initialization(SPIQ_JSON)
                print(
                    f"[spiq] loaded {SPIQ_JSON}: "
                    f"{len(spiq_bundle[1])} relaxed angles, "
                    f"pcirc qpy={spiq_bundle[2].get('pcirc_qpy')}"
                )
            except Exception as exc:
                print(f"[spiq] failed to load {SPIQ_JSON}: {exc}. Falling back to vanilla QAOA.")
                spiq_bundle = None

        use_local = processing != "qpu"
        if spiq_bundle is not None:
            pcirc_spiq, relaxed_ip, spiq_meta = spiq_bundle
            response, init_point, used_eval, min_state_buffer = solve_with_QAOA_spiq(
                qubo, iterations, pcirc_spiq, relaxed_ip, result_dir,
                use_local_simulator=use_local,
                expected_energy=spiq_meta.get("energy_best"),
            )
        else:
            response, init_point, used_eval, min_state_buffer = solve_with_QAOA(
                qubo, iterations, result_dir, reps=TAG, use_local_simulator=use_local)

        if processing == "qpu":
            result_path_prefix = 'ExperimentalAnalysis/IBMQ/QPUPerformance/Results/QPU_Data'
            # Decode the buffered minimum-energy state into join orders right away.
            if min_state_buffer is not None:
                try:
                    buf_resp = _make_spiq_response(None, None, [
                        _make_spiq_sample(s['x'], s['fval'], s['probability']) for s in min_state_buffer['samples']])
                    Postprocessing.postprocess_qiskit_with_readout(
                        buf_resp, card, pred, pred_sel,
                        trial_id=TRIAL_ID, tag=TAG, current_optim=current_optim,
                        iterations=iterations, base_dir=currentPath,
                    )
                except Exception:
                    pass
        else:
            result_path_prefix = 'ExperimentalAnalysis/IBMQ/QPUPerformance/Results/CPU_Data'
            # Save the bitstring/energy/probability distribution of the minimum-energy state.
            if min_state_buffer is not None:
                try:
                    with open(os.path.join(result_dir, 'min_state_readout.csv'), 'w', newline='') as fout:
                        w = csv.writer(fout)
                        w.writerow(['bitstring', 'energy', 'prob'])
                        for s in min_state_buffer['samples']:
                            w.writerow([''.join(str(b) for b in s['x']), s['fval'], s['probability']])
                except Exception:
                    pass

        # Pickled response: read by postprocess_results.py.
        pickle_results(result_path_prefix + '/' + str(iterations) + '_Iterations/' + str(i) + '_predicates-newQUBO/trial' + str(TRIAL_ID), response)


if __name__ == '__main__':
    if config.configuration["ibmq-processing"] != "collected":
        conduct_IBMQ_QPU_experiments()
