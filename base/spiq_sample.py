"""Sample the Clifford state of a SPIQ starting point with stim (no QAOA, works beyond 25 qubits).

Rebuilds the stim circuit from the JSON's problem and formulation, assigns ks_best_raw,
measures every qubit `--shots` times and decodes the samples like a QAOA readout.
Writes <json stem>_readout.csv (Postprocessing.write_readout_csv format) next to the JSON
and prints a summary. Run inside the SPIQ environment, from base/.
"""
import argparse
import json
import os
from collections import Counter

import numpy as np
import stim

import Scripts.Postprocessing as Postprocessing
import Scripts.QUBOGenerator as QUBOGenerator
from clapton.clapton import loss_func
from spiq_initialization import build_vanilla_spiq_objects


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True, help="spiq_initial_point_*.json")
    parser.add_argument("--shots", type=int, default=10240)
    parser.add_argument("--opt_cost", type=int, required=True, help="best plan's cost (brute force)")
    args = parser.parse_args()

    with open(args.json) as f:
        payload = json.load(f)
    prob = payload["problem_input"]
    card, pred, pred_sel = prob["card"], [tuple(p) for p in prob["pred"]], prob["pred_sel"]
    qubo, _ = QUBOGenerator.FORMULATIONS[prob["formulation"]](card, pred, pred_sel)
    op, offset, _, _, stim_circ, _, _, _ = build_vanilla_spiq_objects(qubo, reps=payload["reps"])
    ks = payload["ks_best_raw"]
    n = qubo.get_num_vars()

    # The rebuilt circuit must give the GA's energy exactly, or the samples belong to another state.
    paulis = [p[::-1] for p in op.primitive.paulis.to_labels()]
    e_ising = float(loss_func(ks, paulis, op.primitive.coeffs.real, stim_circ, return_sublosses=True)[2])
    assert abs(e_ising - payload["energy_best"]) < 1e-6 * max(1.0, abs(e_ising)), (e_ising, payload["energy_best"])

    circ = stim_circ.assign(ks).stim_circuit()
    circ.append("M", range(n))  # stim qubit i = qiskit qubit i = QUBO variable i
    shots = circ.compile_sampler(seed=0).sample(args.shots).astype(int)

    energies = [qubo.objective.evaluate(s) for s in shots]
    # Sample mean of the QUBO energy must match the Clifford expectation (checks the bit order).
    se = np.std(energies) / np.sqrt(len(energies))
    print(f"mean sampled energy {np.mean(energies):.4f} vs SPIQ expectation {payload['energy_best_qubo']:.4f} (se {se:.4f})")
    assert abs(np.mean(energies) - payload["energy_best_qubo"]) < 5 * se + 1e-9

    counts = Counter(tuple(s) for s in shots)
    solutions = [[list(b), c, qubo.objective.evaluate(list(b)), "".join(map(str, b)), c / args.shots]
                 for b, c in counts.items()]
    best_for_time, rows = Postprocessing.readout([solutions, 0.0], card, pred, pred_sel, {})
    csv_path = args.json.replace(".json", "_readout.csv")
    Postprocessing.write_readout_csv(csv_path, best_for_time, rows)

    # Valid plan: column j of the table block has j+2 ones, and each column contains the previous one.
    R = len(card)
    v = shots[:, :R * (R - 2)].reshape(-1, R, R - 2)
    valid = (v.sum(axis=1) == np.arange(2, R)).all(axis=1) & (v[:, :, :-1] <= v[:, :, 1:]).all(axis=(1, 2))

    raw = np.array([r[2] for r in rows if not r[4]])
    fb = np.array([r[2] for r in rows if r[4]])
    print(f"{prob['formulation']} input{payload['input_idx']}: {n} qubits, {len(ks)} angles, "
          f"SPIQ energy {payload['energy_best_qubo']:.4f}, distinct states {len(counts)}, valid {valid.mean():.3f}")
    for name, c in (("raw", raw), ("fallback", fb)):
        top = ", ".join(f"{k} ({v / len(c):.1%})" for k, v in Counter(c.tolist()).most_common(4))
        print(f"  {name}: share at best plan {(c == args.opt_cost).mean():.4f}, mean cost {c.mean():.1f}, "
              f"min {c.min()}; most common {top}")
    print(f"wrote {csv_path}")


if __name__ == "__main__":
    main()
