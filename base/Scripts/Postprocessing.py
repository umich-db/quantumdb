"""Decode sampled bitstrings into join orders and cost them (paper §3.3).

For every sampled bitstring:
  1. The relation-join part of the bitstring is reshaped into an R x (J-1)
     assignment matrix and multiplied by a weight vector that favours earlier
     joins, giving one score per relation (higher = joined earlier).
  2. Sorting the scores gives the "raw" left-deep join order (fallback=False).
  3. The fallback of Schönberger et al. walks the query graph in score order,
     preferring relations connected by a predicate to avoid cross products
     (fallback=True).
Both candidate plans are costed classically (sum of intermediate
cardinalities) and written to `readout_summary*.csv`, which
`visualization.rmd` turns into Table 1 of the paper.
"""

import csv
import os
import time
from math import inf

import numpy as np


def get_selectivity_for_new_relation(join_order, j, pred, pred_sel):
    """Combined selectivity of all predicates between join_order[j] and the relations joined before it."""
    sel = 1
    new_relation = join_order[j]
    for i in range(j):
        relation = join_order[i]
        if (relation, new_relation) in pred:
            sel = sel * pred_sel[pred.index((relation, new_relation))]
        elif (new_relation, relation) in pred:
            sel = sel * pred_sel[pred.index((new_relation, relation))]
    return sel


def get_intermediate_costs_for_join_order(join_order, card, pred, pred_sel, card_dict, verbose=False):
    """Intermediate result cardinalities of a left-deep plan, excluding the order-independent final join.

    `card_dict` memoises cardinalities by join-order prefix across calls.
    """
    int_costs = []
    join_order = join_order.copy()
    # The first two relations commute; normalise so both orders share memo entries.
    if join_order[0] > join_order[1]:
        join_order[0], join_order[1] = join_order[1], join_order[0]
    prev_join_result = card[join_order[0]]
    for j in range(1, len(card)-1):
        jo_hash = str(join_order[0:j+1])
        if jo_hash in card_dict:
            int_card = card_dict[jo_hash]
        else:
            sel = get_selectivity_for_new_relation(join_order, j, pred, pred_sel)
            int_card = prev_join_result * card[join_order[j]] * sel
            card_dict[jo_hash] = int_card
        prev_join_result = int_card
        int_costs.append(int_card)
    if verbose:
        print(int_costs)
    return int_costs


def get_costs_for_leftdeep_tree(join_order, card, pred, pred_sel, card_dict, verbose=False):
    """Plan cost C_out: sum of intermediate result cardinalities."""
    return sum(get_intermediate_costs_for_join_order(join_order, card, pred, pred_sel, card_dict, verbose=verbose))


def get_raw_join_order(cost_vector):
    """Relations sorted by descending score (earliest-joined first)."""
    join_order = np.argsort(cost_vector).tolist()
    join_order.reverse()
    return join_order


def postprocess_join_order(raw_join_order, cost_vector, num_relations, pred):
    """Fallback plan: greedily extend the join order with the highest-scored relation
    connected to the current prefix by a predicate; only take a cross product
    (highest-scored remaining relation) when no connected relation is left."""
    join_order = [raw_join_order[0]]
    while len(join_order) < num_relations:

        applicable_predicates = [pred_tuple for t in join_order for pred_tuple in pred if t in pred_tuple]
        neighborhood_indices = [t for t in set(sum(applicable_predicates, ())) if t not in join_order]

        if len(neighborhood_indices) != 0:
            best_neighbor_relation = neighborhood_indices[np.argmax(cost_vector[neighborhood_indices])]
            join_order.append(best_neighbor_relation)
        else:
            global_indices = [x for x in raw_join_order if x not in join_order]
            best_global_relation = global_indices[np.argmax(cost_vector[global_indices])]
            join_order.append(best_global_relation)
    return join_order


def readout(response, card, pred, pred_sel, card_dict):
    """Decode every sampled bitstring into a raw and a fallback join order and cost both.

    Args:
        response: [solutions, opt_time_ms] where each solution is
            [bitlist, count, energy, bitstring, probability].
        card, pred, pred_sel: the join-ordering problem.
        card_dict: memo dict for intermediate cardinalities (may be shared).

    Returns:
        (best_solutions_for_time, solutions). Each solution row is
        [bitstring, join_order, cost, time_ms, used_fallback, energy, count, probability];
        `best_solutions_for_time` holds only rows that improved the best cost so far.
        Every bitstring is expanded `count` times, so rows are weighted by sample frequency.
    """
    start = time.time()
    bitstrings = []
    for solution in response[0]:
        bit = solution[0]
        energy = solution[2]
        occ = solution[1]
        stringbit = solution[3]
        probability = solution[4]
        for _ in range(occ):
            bitstrings.append((bit, energy, stringbit, occ, probability))

    # Weights (R-2, ..., 1): relations present in earlier joins score higher.
    weight_vector = np.arange(1, len(card)-1)
    weight_vector = weight_vector[len(card)-3::-1]

    best_solutions_for_time = []
    best_costs = inf

    solutions = []

    num_relations = len(card)

    for i in range(len(bitstrings)):
        bitstring, energy, stringbit, occ, probability = bitstrings[i]

        # Keep only the v[t, j] block (R x (R-2)); predicate variables follow it.
        bitstring = bitstring[:len(card)*(len(card)-2)]
        partial_bitstrings = np.array_split(bitstring, len(card))
        cost_vector = np.array(partial_bitstrings).dot(weight_vector)

        raw_join_order = get_raw_join_order(cost_vector)

        costs = get_costs_for_leftdeep_tree(raw_join_order, card, pred, pred_sel, card_dict)

        solution = [stringbit, raw_join_order, int(costs), (time.time()-start)*1000, False, energy, occ, probability]
        solutions.append(solution)
        if costs < best_costs:
            best_costs = costs
            best_solutions_for_time.append(solution)

        # Fallback
        join_order = postprocess_join_order(raw_join_order, cost_vector, num_relations, pred)
        costs = get_costs_for_leftdeep_tree(join_order, card, pred, pred_sel, card_dict)
        solution = [stringbit, join_order, int(costs), (time.time()-start)*1000, True, energy, occ, probability]
        solutions.append(solution)
        if costs < best_costs:
            best_costs = costs
            best_solutions_for_time.append(solution)

    return best_solutions_for_time, solutions


def write_readout_csv(csv_path, best_for_time, all_solutions):
    """Write the two `readout` result tables into one CSV, each preceded by a '# ...' marker row."""
    columns = ["join_order", "cost", "time_ms", "used_fallback", "energy", "count", "probability"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for title, index_name, rows in (("# best_solutions_for_time", "rank", best_for_time),
                                        ("# all_solutions", "index", all_solutions)):
            if title == "# all_solutions":
                w.writerow([])
            w.writerow([title])
            w.writerow(["bitstring", index_name] + columns)
            for idx, (bitstring, *rest) in enumerate(rows):
                w.writerow([bitstring, idx] + rest)


def postprocess_qiskit_with_readout(
    qaoa_result, card, pred, pred_sel,
    card_dict=None,
    scale=1000,
    opt_time_ms=0.0,
    trial_id=4,
    tag=4,
    current_optim=0,
    iterations=10000,
    base_dir=None,
    shots=10240,
):
    """Run `readout` on a result exposing `.samples` (each with .x, .fval, .probability)
    and save it to <base_dir>/iterations_*/reps_*/<optim>/trial_<id>/readout_summary.csv.

    `scale` is unused and kept only for call-site compatibility.
    """
    if card_dict is None:
        card_dict = {}

    if base_dir is None:
        base_dir = os.path.join(".", "Week84", "ExperimentalAnalysis", "IBMQ", "QPUPerformance", "Results", "CPU_Data")
    result_dir = os.path.join(base_dir, f"iterations_{iterations}", f"reps_{tag}", f"{current_optim}", f"trial_{trial_id}")
    os.makedirs(result_dir, exist_ok=True)
    csv_path = os.path.join(result_dir, "readout_summary.csv")

    solutions = []
    for s in qaoa_result.samples:
        bitlist = [int(b) for b in s.x]
        occ = round(s.probability*shots)  # recover shot counts from probabilities
        stringbit = "".join(str(b) for b in bitlist)
        solutions.append([bitlist, occ, float(s.fval), stringbit, s.probability])

    best_for_time, all_solutions = readout([solutions, float(opt_time_ms)], card, pred, pred_sel, card_dict)
    write_readout_csv(csv_path, best_for_time, all_solutions)
    print(f"save to /{result_dir}/readout_summary.csv")

    return best_for_time, all_solutions
