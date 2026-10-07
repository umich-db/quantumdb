# Change log: what changed and why

Newest first. Each entry says what changed, why it was needed, and how it was checked.
See `RESULTS_INDEX.md` for which week folder holds which run.

---

## 2026-09-30: Optimal-ratio tables for the seeded multi-start runs

**Files:** `graphs/seeded-multi-spiq.rmd`

**What changed:** for each of P1–P3 (Week93–95), there are `qcdkm.rmd`-style
`cost_energy_boxplot_prob` chunks for the final readout and for the
first-iteration readout. Each is run twice, with raw decoding
(`used_fallback = FALSE`) and with fallback decoding (`TRUE`). The file ends
with a `knitr::kable` summary of the optimal ratio for every problem, stage and
decoding. `target` is each problem's true optimal cost, brute-forced over all
left-deep orders with `Postprocessing.get_costs_for_leftdeep_tree`:
P1 = 15, P2 = 315, P3 = 39.

**Why:** join-order quality (share of samples at the optimal plan) is the
paper's headline metric, alongside energy. The `qcdkm.rmd` targets were
hard-coded and don't match the current problems; for example, it uses 39 for
problem 2, whose optimum is 315.

**Result (share of samples at the optimal cost; raw = fallback in every case):**

| Problem | First iteration (SPIQ start) | Final |
|---|---|---|
| P1 | 0.502 | 0.507 (the rest is cost 30) |
| P2 | 0.000 | 0.0001 (99.99% at cost 465, the second-best plan) |
| P3 | 0.121 | 0.126 |

**Checks:** the whole file knits with `rmarkdown::render` without errors.

---

## 2026-09-29: Multi-start picks starting points from different regions of the landscape

**Files:** `clapton/clapton.py`, `base/spiq_initialization.py`, `base/test_select_diverse.py`, README

**What changed**
- **Independent GA searches.** `genetic_algorithm` now takes `seed`, and each
  parallel GA `m` gets `random_seed = seed + m`. Previously every GA used
  `random_seed=0`. The main GA keeps seed 0, so its search is identical to before.
- **Candidate pool from every search.** `claptonize` returns `pool_xs` / `pool_src`:
  each GA's last-round elite plus its per-generation best solutions. These
  replace the old `xs, losses` (elite only), and the other GAs' histories are
  no longer thrown away.
- **Diversity-aware selection** (`_select_diverse`), replacing `_top_k_unique`:
  1. Merge k-vectors that prepare the same quantum state (stim
     `canonical_stabilizers()`), keeping the lowest-energy one.
  2. Keep states within `--energy_window` of the best
     (`E ≤ E_best + w·|E_best|`, default 0.25).
  3. Pick greedily to maximise the minimum Hamming distance in `k` to the points
     already chosen.
  Candidate 0 is always the global best.
- **New flags:** `--seed` (default 0) and `--energy_window` (default 0.25).
  `--n_starts` now really controls the number of independent searches.
- **New JSON fields:** `pool_size`, `pool_distinct_states`, `pool_in_energy_window`,
  `candidate_min_hamming`, `candidate_source_ga`, `seed`, `n_starts`, `energy_window`.

**Why**
- On P3, the 3 multi-start runs (Week92) all began at the same Ising energy
  (-11.93) and ended at 12.8–13.5 (QUBO). An earlier single-start run (Week60) on
  the *same* QUBO and circuit started from a different Clifford point at 9.87 and
  finished at 9.79. Starting quality dominated, because COBYLA only improved
  things by 0.3–1.0 from any start.
- Root cause: every GA used `random_seed=0` and none got an initial population
  in round 1, so the `n_starts` "independent" searches were the same search run
  several times. That is why P1's elite collapsed to one point at
  `n_gens=2000`, and why P3's candidates were near-copies of one optimum.
- Many candidates that tie on energy prepare the same state, so starts spent on
  them are wasted. Energy alone can't tell them apart; a canonical state ID can.
- Hamming distance in `k` is distance in the space COBYLA searches, so max–min
  selection spreads the starts across different local neighbourhoods.
- The energy window makes the quality/diversity trade-off explicit: a slightly
  worse Clifford point in another basin can win after optimisation.

**Checks:** see "Verification" below.

---

## 2026-09-24: Postprocessing re-simulates SPIQ runs on their own circuit

**Files:** `base/IBMQExperiments.py`, `base/postprocess_results.py`

**What changed:** SPIQ runs save `pcirc.qpy` into the trial directory.
`postprocess_results.py` loads it (or `--pcirc_qpy`) and binds all the per-gate
angles into it. If the parameter count doesn't match the circuit, it stops with
an error.

**Why:** postprocessing used to bind SPIQ's per-gate angles into the stock
`QAOAAnsatz`, using only the first `2·reps` of them. So `readout_summary_eval<k>.csv`
did not show the SPIQ state at all.

---

## 2026-09-23 / 24: Multi-start SPIQ → QAOA

**Files:** `clapton/clapton.py`, `base/spiq_initialization.py`, `base/IBMQExperiments.py`,
`scripts/run_ibmq.sh`, README

**What changed**
- SPIQ exports up to `--n_candidates` Clifford points (`relaxed_initial_points`,
  `candidate_energies`, `candidate_ks`).
- QAOA optimises from `--spiq_starts` of them, each with the full
  `--iterations`, and keeps the lowest-energy run.
- Per-start logs are written to `energy_per_iteration_…_start{j}.csv`, and the
  winning run is copied to the standard file name, so downstream code is
  unchanged.
- Both flags default to 1, which reproduces the old single-start behaviour.

**Why:** the SPIQ paper initialises from a *set* of good Clifford points rather
than only the best one. A single start is exposed to one bad basin.

**Known limitation found afterwards (fixed on 2026-09-29):** at `n_gens=2000` the
candidate set collapsed to one point on P1. Week90 ran 1 start even with
`--n_candidates 5`.

---

## Verification

### 2026-09-29 diversity changes

- `base/test_select_diverse.py` passes (run in the container). It checks: states
  are merged, the energy window is applied, max–min ordering, and that the best
  point comes first.
- All P1 runs below used `--reps 2`, output to `/tmp` in the container:

| Check | Command flags | Before | After |
|---|---|---|---|
| No regression | `--n_gens 2000 --n_starts 1 --n_proc 8 --n_candidates 1 --seed 0` | best Ising -2.503626 | **-2.503626** (identical) |
| Independent GAs | `--n_gens 200 --n_starts 4 --n_candidates 5` | 4 identical GAs | GA 2 found **-2.548935**, better than GA 0's -2.503626; picks came from GAs 2, 0, 1, 1, 2 |
| Collapse fixed | `--n_gens 2000 --n_starts 4 --n_candidates 5` | 1 candidate (80 elite, 1 distinct) | **5 candidates**. Pool: 544 k-vectors, **32 distinct states**, 27 in the window. Minimum Hamming distance between picks: 31, 30, 28, 28 of 40 gates. Source GAs: 2, 1, 2, 0, 3 |

**Behaviour change to be aware of:** with the default `--n_starts 4`, the SPIQ
best point is now the best of 4 *independent* searches. So even single-start
results can differ from, and be better than, earlier runs; P1 improved from
-2.5036 to -2.5489. To reproduce an old single-start result exactly, use
`--n_starts 1 --seed 0`.

**Existing bug found, not fixed:** `--n_starts 1` with the default
`--n_proc 32` crashes in `clapton` `eval_xs_terms_mp` / `n_to_dits`
("n cannot be represented in this basis"), because there are more processes
than work to split. Pass `--n_proc 8` or lower for single-GA runs.

### 2026-09-29/30 runs: diverse multi-start on all three problems (Week93–95)

Settings: `--n_starts 8 --seed 0 --n_gens 2000 --energy_window 0.25
--n_candidates 10`, then `--spiq_starts 3` with COBYLA at **1000 iterations**,
reps 2. The run logs are in `logs/`.

| Problem | Distinct states in pool | Spread of picks (min Hamming) | SPIQ best Ising (before → now) | QAOA best QUBO (before → now) | Exact |
|---|---|---|---|---|---|
| P1 | 123 | 37 … 19 of 40 gates | -2.504 → **-2.935** | 1.544 (Week90) → **1.125** | 1.031 |
| P2 | 1578 | 95 … 25 of 116 | -12.155 → **-14.918** | 8.254 (Week91) → **5.550** | 4.766 |
| P3 | 3143 | 209 … of 268 | -11.935 → **-13.372** | 12.825 (Week92) → **12.373** | 2.725 |

**Findings**
- The gain comes from the independent GA seeds: the best Clifford point
  improved on every problem, and every QAOA winner was start0, i.e. that best
  point. P1 and P2 now end much closer to the exact ground state.
- The spread-out starts (start1, start2) were valid and far apart, but none
  beat start0 on this landscape. On P3, start2 came close (12.52 vs 12.37).
- P3 is still above the earlier Week60 single-start run (9.79). That run began
  from a Clifford point at QUBO 9.87, and no search found anything that good
  here (best 12.41 at the start).
- P2 and P3 used the full 1000 evaluations, so they may not have converged.
  P1 converged in fewer than 800.
