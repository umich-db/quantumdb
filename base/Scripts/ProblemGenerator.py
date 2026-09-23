"""Load a join-ordering problem (the query graph of paper Fig. 1) from disk.

A problem directory contains three JSON files:
    card.txt      relation cardinalities, e.g. [10, 15, 20]
    pred.txt      join predicates as relation-index pairs, e.g. [[0, 1], [1, 2]]
    pred_sel.txt  predicate selectivities aligned with pred.txt, e.g. [0.1, 0.1]
"""

import json
import os


def get_join_ordering_problem(problem_path):
    """Return (card, pred, pred_sel) for the problem stored in `problem_path`; predicates become tuples."""
    card = load_from_path(problem_path + "/card.txt")
    pred = [tuple(p) for p in load_from_path(problem_path + "/pred.txt")]
    pred_sel = load_from_path(problem_path + "/pred_sel.txt")
    return card, pred, pred_sel


def load_from_path(problem_path):
    """Load a JSON file; returns None if it does not exist."""
    data_file = os.path.abspath(problem_path)
    if os.path.exists(data_file):
        with open(data_file) as file:
            return json.load(file)
