"""QUBO encoding of a left-deep join-ordering problem (paper §3.1).

Implements the native, threshold-free encoding of Schönberger, Trummer and
Mauerer (VLDB'24) adapted for QAOA: only (R + P)(J - 1) binary variables and
no slack variables, because intermediate-result cost is approximated by the
square of the logarithmic intermediate cardinality instead of MILP-style
threshold inequalities.

Variable layout (docplex creates the matrices in this order, so this is also
the qubit / bitstring order used downstream):
    v[t, j]         relation t is part of the join tree at join j
    pred_vars[p, j] predicate p is applicable at join j
with R relations, P predicates and J - 1 = R - 2 encoded joins. The last join
always contains every relation (its output size is order-independent), so it
is not encoded.
"""

import numpy as np
from docplex.mp.model import Model
from qiskit_optimization.translators import from_docplex_mp


def get_log_values(coeff, num_decimal_pos, use_rounding=True):
    """Return log10 of every value in `coeff`, optionally rounded to `num_decimal_pos` decimals."""
    if use_rounding:
        log_coeff = np.around(np.log10(coeff), num_decimal_pos)
    else:
        log_coeff = np.log10(coeff)
    return log_coeff.tolist()


def generate_IBMQ_QUBO_for_left_deep_trees_v2(card, pred, pred_sel, penalty_scaling=1):
    """Build the join-ordering QUBO as a qiskit `QuadraticProgram`.

    Args:
        card: relation cardinalities, indexed by relation id.
        pred: list of (i, j) relation pairs that have a join predicate.
        pred_sel: selectivity of each predicate, aligned with `pred`.
        penalty_scaling: multiplier on the validity-penalty weight.

    Returns:
        (qubo, penalty_weight): H = penalty_weight * (H_A + H_B + H_pred) + H_cost.
    """
    # Work in log space so products of cardinalities/selectivities become sums.
    card = get_log_values(card, 0, use_rounding=False)
    pred_sel = get_log_values(pred_sel, 0, use_rounding=False)

    print("Card:")
    print(card)
    print("Pred sel:")
    print(pred_sel)

    model = Model('docplex_model')

    num_relations = len(card)
    num_pred = len(pred_sel)
    num_joins = len(card) - 2

    v = model.binary_var_matrix(num_relations, num_joins)

    # Join j must contain exactly j + 2 relations.
    b = np.arange(2, num_joins+2).tolist()

    # Incentivise that the right number of relations is present for every join (i.e., 2 for join 1, 3 for join 2, ...)
    H_A = model.sum((b[j] - model.sum(v[(t, j)] for t in range(num_relations)))**2 for j in range(num_joins))

    # Incentivise that, once joined, a relation is always part of subsequent joins
    H_B = model.sum(model.sum(v[(t, j-1)] - v[(t, j-1)]*v[(t, j)] for j in range(1, num_joins)) for t in range(num_relations))

    # Incentivise that a predicate is only applicable for a join if both associated relations are present
    pred_vars = model.binary_var_matrix(num_pred, num_joins)
    H_pred_a = model.sum(model.sum(pred_vars[(p, j)] - pred_vars[(p, j)] *v[(pred[p][0], j)] for p in range(num_pred)) for j in range(num_joins))
    H_pred_b = model.sum(model.sum(pred_vars[(p, j)] - pred_vars[(p, j)] *v[(pred[p][1], j)] for p in range(num_pred)) for j in range(num_joins))
    H_pred = H_pred_a + H_pred_b

    H_cost = 0
    penalty_weight = 0

    # Cost: squared log intermediate cardinality of every join,
    # log|R_join| = sum(log card of present relations) + sum(log sel of applicable predicates).
    # Selectivities are < 1 (negative logs), so the optimizer is rewarded for applying predicates.
    for j in range(num_joins):
        penalty_weight = penalty_weight + 1
        H_thres = (model.sum(card[t]*v[(t, j)] for t in range(num_relations)) + model.sum(pred_sel[p] * pred_vars[(p, j)] for p in range(num_pred)))**2
        H_cost = H_cost + H_thres

    # Penalty weight = number of encoded joins, scaled by the caller.
    print("Vanilla penalty weight: " + str(penalty_weight))
    penalty_weight = penalty_weight * penalty_scaling

    H_valid = H_A + H_B + H_pred

    H = penalty_weight * H_valid + H_cost

    model.minimize(H)

    qubo = from_docplex_mp(model)

    return qubo, penalty_weight
