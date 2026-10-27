"""Self-check for the "qaoa" QUBO formulation (run inside the SPIQ environment, from base/).

For P1-P5: the QUBO uses R(R-2) qubits, its ground state is a valid plan, and that plan decodes
to the true optimal cost. Also checks that a repeated predicate pair applies both selectivities.
"""
import itertools

import numpy as np

import Scripts.Postprocessing as Postprocessing
import Scripts.ProblemGenerator as ProblemGenerator
import Scripts.QUBOGenerator as QUBOGenerator


def brute_force_ground(qubo, chunk=1 << 20):
    """Lowest-energy bitstring over all 2^n, evaluated in vectorised chunks (2^24 takes ~1 min)."""
    n = qubo.get_num_vars()
    lin = qubo.objective.linear.to_array()
    quad = qubo.objective.quadratic.to_array()
    const = qubo.objective.constant
    shifts = np.arange(n)
    best_e, best_x = np.inf, None
    for start in range(0, 1 << n, chunk):
        idx = np.arange(start, min(start + chunk, 1 << n))
        x = ((idx[:, None] >> shifts) & 1).astype(np.float64)  # bit k of idx = variable k
        e = const + x @ lin + np.einsum("ij,ij->i", x @ quad, x)
        k = int(np.argmin(e))
        if e[k] < best_e:
            best_e, best_x = e[k], x[k].astype(int).tolist()
    assert abs(qubo.objective.evaluate(best_x) - best_e) < 1e-6
    return best_x


for i in range(5):
    card, pred, pred_sel = ProblemGenerator.get_join_ordering_problem(
        f"ExperimentalAnalysis/IBMQ/QPUPerformance/Problems/JSON/{i}_predicates")
    R, J = len(card), len(card) - 2
    qubo, _ = QUBOGenerator.generate_qaoa_qubo_left_deep(card, pred, pred_sel)
    assert qubo.get_num_vars() == R * J, (i, qubo.get_num_vars())

    ground = brute_force_ground(qubo)
    v = np.array(ground).reshape(R, J)
    assert all(v[:, j].sum() == j + 2 for j in range(J)) and (v[:, :-1] <= v[:, 1:]).all(), (i, v)

    opt = min(Postprocessing.get_costs_for_leftdeep_tree(list(p), card, pred, pred_sel, {})
              for p in itertools.permutations(range(R)))
    _, solutions = Postprocessing.readout([[[list(ground), 1, 0.0, "", 1.0]], 0.0], card, pred, pred_sel, {})
    assert solutions[0][2] == int(opt), (i, solutions[0], opt)
    print(f"input{i}: {R} tables, {R * J} qubits, optimal cost {opt}, ground energy {qubo.objective.evaluate(ground)}")

    if i == 2:  # P3 lists (1, 2) twice: 15 * 20 * 0.2 * 0.4 * 0.6 = 14.4, plus 15 -> 29.4
        assert abs(opt - 29.4) < 1e-9, opt
print("ok")
