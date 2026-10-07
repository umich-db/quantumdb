"""Self-check for spiq_initialization._select_diverse (run inside the SPIQ environment, from base/)."""
from spiq_initialization import _select_diverse


def c(ks, energy, state, src=0):
    return {"ks": ks, "src": src, "energy": energy, "state": state}


cands = [
    c([0, 0, 0, 0], -10.0, "A"),     # global best
    c([1, 0, 0, 0], -10.0, "A"),     # same state as best -> dropped
    c([0, 0, 0, 1], -9.5, "B"),      # close to best (Hamming 1)
    c([3, 3, 3, 3], -8.5, "C"),      # far from best (Hamming 4), inside window
    c([2, 2, 2, 2], -5.0, "D"),      # far, but outside the 25% window (> -7.5)
]
picked, n_states, n_window = _select_diverse(cands, 3, 0.25)
assert [p["state"] for p in picked] == ["A", "C", "B"], picked
assert [p["min_hamming"] for p in picked] == [None, 4, 1], picked
assert (n_states, n_window) == (4, 3)
assert _select_diverse(cands, 10, 0.25)[0][-1]["state"] == "B"   # window caps the count
assert len(_select_diverse(cands, 1, 0.25)[0]) == 1
print("ok")
