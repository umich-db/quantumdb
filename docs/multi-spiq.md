# Multi-point SPIQ initialization for join-order QAOA

How SPIQ initialization evolved in this repository:
1. what the original SPIQ paper does;
2. how our first implementation adapted it;
3. the first multi-point version (Week90–92) and why it barely changed QAOA's results;
4. the seeded, diversity-aware version (Week93–95) and why it works better.

Related records:
- `CHANGELOG.md`: code changes, with dates.
- `RESULTS_INDEX.md`: which week holds which run.
- `problem-formulation.md`: the QUBO issues that limit P2.

Problems used throughout (QUBO scale, lower is better):

| | Shape | Qubits | Relaxed parameters (reps = 2) | Exact ground-state energy | Optimal plan cost |
|---|---|---|---|---|---|
| P1 | 3 relations, 2 predicates | 5 | 40 | 1.031 | 15 |
| P2 | 4 relations, 2 predicates | 12 | 116 | 4.766 | 315 |
| P3 | 4 relations, 6 predicates | 20 | 268 | 2.725 | 39 (evaluator) / 29.4 (QUBO); see `problem-formulation.md` §2.3 |

---

## 1. The original SPIQ paper

Bharadwaj, Hou, Li, Ravi, *"Scalable Clifford-Based Classical Initialization for the Quantum Approximate Optimization Algorithm"*, arXiv:2602.14327.

- **Relaxed ansatz (§II-C).** SPIQ uses multi-angle QAOA (ma-QAOA): every cost and mixer term gets its own angle, giving (m+n)·p parameters instead of QAOA's 2p.
- **Clifford restriction.** Each angle is limited to a multiple of π/2. Every candidate state is then a stabilizer state, so its energy can be computed efficiently on a classical machine.
- **Search (§III-B).** A gradient-free genetic algorithm (PyGAD) searches the Clifford angles. The paper's budget is "48 hours of search across four independent starts".
- **Multi-start (§III-C).** The paper does not use only the single best Clifford point. Its stated reason: "a single optimization run … risks converging to a sharp or undesirable local minimum". It seeds several QAOA runs from a set of good points, chosen by one of two strategies:
  - **Fixed-interval selection:** sort the candidates by energy and take points at regular intervals.
  - **K-GAPS** (K-means Gradient-Aware Point Selection):
    - k-means clustering on a circular embedding (cos θ, sin θ) of the angles, so the points come from structurally distinct regions;
    - plus a gradient-norm filter, using the parameter-shift rule, that discards points sitting in flat regions.
- **Optimizer (§IV-C).** COBYLA, starting from the Clifford points.

## 2. Our original implementation (single-point SPIQ)

`base/spiq_initialization.py` with the vendored `clapton/` library, then `base/IBMQExperiments.py`.

**What matches the paper:**
- The QAOA ansatz for the join-order QUBO is decomposed and then relaxed (`clapton.relax_qaoa_parameters`), so every Rz gate gets its own parameter (the ma-QAOA idea).
- Each parameter is restricted to k·π/2 with k ∈ {0, 1, 2, 3}. The circuit is converted to stim and searched with clapton's PyGAD GA (`claptonize`).
- COBYLA then optimises every per-gate angle of the relaxed circuit (`pcirc`), starting from the Clifford point.

**What we changed or added for this problem:**
- **Problem.** The Hamiltonian is the native join-order QUBO (Schönberger et al.), mapped to Ising form, rather than the paper's benchmark QUBO, PUBO and PCBO problems.
- **Angle recovery.** Relaxation puts each gate's coefficient into the parameter *name*. We therefore evaluate the true applied multiplier numerically and keep its sign; using `abs(mult)` swaps S and S†. This makes the qiskit circuit reproduce stim's energy exactly. The details are in README §5.
- **Sanity checks.** A qiskit Statevector check is done in SPIQ, and a shot-based check in QAOA (tolerance 0.25).
- **Budget.** `--n_gens 2000` means clapton gets 1000 generations, with population 100 and `--n_starts 4` parallel GAs. That is far smaller than the paper's 48 hours.
- **Single point.** Only the best Clifford point (`relaxed_initial_point`) was passed to QAOA. **There was no multi-start.** This was the main gap from the paper.
- **Two environments.** SPIQ needs a newer qiskit stack (aer and algorithms) than the QAOA driver.

## 3. First multi-point SPIQ (Week90–92)

**Change** (2026-09-23/24; see the CHANGELOG):
- `claptonize` returns the final-round elite of the GA: the top 20% of each population, 4 × 20 = 80 points.
- `spiq_initialization.py --n_candidates K` exports the K best *distinct k-vectors* from that elite, sorted by loss.
- `IBMQExperiments.py --spiq_starts S` runs COBYLA from S of them, each with the full iteration budget, and keeps the run with the lowest energy.

Runs: `--n_gens 2000`, 10000 COBYLA iterations, reps 2. P1 used `--n_candidates 5 --spiq_starts 3`; P2 and P3 used `--n_candidates 10 --spiq_starts 3`.

| Problem | Week | Candidates exported | Candidate Ising energies | Best QAOA energy per start | Kept | Single-start reference |
|---|---|---|---|---|---|---|
| P1 | 90 | **1** (of 5 requested) | -2.504 | 1.544 (1 start only) | 1.544 | — (same as single-start) |
| P2 | 91 | 10 | **all -12.155** | 8.254 / 8.277 / 8.271 | 8.254 | 8.263 (Week88) |
| P3 | 92 | 10 | 6 tied at -11.935, the rest down to about -9 | 13.524 / **12.825** / 13.197 | 12.825 | **9.786** (Week60) |

**Result:** essentially no gain over single-start SPIQ.
- On P1 multi-start never ran: only one start existed.
- On P2 the three starts finished within 0.03 of each other.
- On P3 multi-start finished worse than an older single-start run.

## 4. Why QAOA performance barely changed

1. **The four GA "starts" were the same search.**
   - clapton hard-coded `pygad.GA(random_seed=0)` for every parallel GA, and no GA gets an initial population in round 1.
   - So `--n_starts 4` ran one search four times. The elite was four copies of one converged population.
   - This is the root cause, found 2026-09-28. The paper's "four independent starts" were never independent here.
2. **Converged populations are not diverse.** By generation 1000 a GA population is almost entirely copies of its best individual.
   - P1: all 80 elite points were the same k-vector, so `--n_candidates 5` produced one candidate. A 20-generation probe gave 16 distinct points; the 2000-generation run gave 1.
3. **Distinct k-vectors are not distinct starting points.**
   - The 10 P2 candidates all have exactly the same energy, and 6 of P3's top 10 tie.
   - Different k-vectors can prepare the same quantum state, or states in the same basin. The selection only removed *identical* vectors, so the starts were near-copies.
4. **COBYLA refines locally, so the starting point decides the result.**
   - From any start COBYLA improved the energy by only about 0.3–1.0 (P3: 13.87 → 12.82 at best).
   - Week60 beat Week92 on P3 only because it started from a better Clifford point: QUBO 9.87 vs 13.87, on the same QUBO and the same circuit. Re-simulating both points on the shared circuit gave exactly these values.
   - Several near-identical starts cannot escape one basin.
5. **For P2, the QUBO itself caps the optimal ratio.**
   - The P2 ground state (E = 4.766) is an *infeasible* encoding: join 2 has only 2 relations. It decodes to the second-best plan, cost 465. Details are in `problem-formulation.md` §2.1 and §4.1.
   - Even perfect initialization drives QAOA toward that plan. Initialization cannot fix this.

## 5. Seeded, diversity-aware multi-point SPIQ (Week93–95)

**Change** (2026-09-29; code in `clapton/clapton.py` and `base/spiq_initialization.py`):

1. **Independent searches.** GA *m* is seeded with `seed + m` (`--seed`, default 0).
   - The main GA keeps seed 0, so `--n_starts 1 --seed 0` reproduces the old result exactly. Checked: P1 gives -2.503626 both before and after.
   - The runs used `--n_starts 8`.
2. **A pool from every search.** `claptonize` returns every GA's last-round elite *and* its per-generation best solutions over all rounds. Before, the other GAs' histories were thrown away.
3. **Selection** (`_select_diverse`):
   1. **Merge points that prepare the same state.** Each k-vector is keyed by stim's `canonical_stabilizers()`, and only the lowest-energy vector per state is kept.
   2. **Energy window.** Keep states with E ≤ E_best + 0.25·|E_best| (`--energy_window`).
   3. **Greedy max–min Hamming selection.** Start from the global best. Then repeatedly add the state whose smallest Hamming distance in k to the points already chosen is largest. "Hamming distance" here is the number of gates with different angles.

**How this relates to the paper's strategies:**
- It shares K-GAPS's goal of picking points from structurally distinct regions. It is not K-GAPS.
  - There is no k-means and no gradient-norm filter.
  - Hamming distance treats every angle change as distance 1. K-GAPS's (cos θ, sin θ) embedding treats π/2 as closer than π.
- It adds two things the paper does not describe: merging points by quantum state, and an explicit energy window.
- The commit `4600dd3a` is titled "k-gaps based", but the code is the max–min Hamming selection described here.

**Runs:** `--n_starts 8 --seed 0 --n_gens 2000 --energy_window 0.25 --n_candidates 10 --spiq_starts 3`, COBYLA with **1000** iterations, reps 2.

| Problem | Week | Pool (k-vectors / distinct states / in window) | Min Hamming distance of picks to earlier picks | SPIQ best Ising: Week90–92 → now | Best QAOA energy per start | Kept | Best QAOA: Week90–92 → now | Optimal ratio (final) |
|---|---|---|---|---|---|---|---|---|
| P1 | 93 | 2223 / 123 / 93 | 37 … 19 of 40 | -2.504 → **-2.935** | **1.125** / 1.662 / 1.544 | start 0 | 1.544 → **1.125** | 0.507 |
| P2 | 94 | 4369 / 1578 / 609 | 95 … 25 of 116 | -12.155 → **-14.918** | **5.550** / 8.166 / 8.280 | start 0 | 8.254 → **5.550** | 0.0001 |
| P3 | 95 | 3244 / 3143 / 1249 | 209 … of 268 | -11.935 → **-13.372** | **12.373** / 14.923 / 12.515 | start 0 | 12.825 → **12.373** | 0.126 |

Gap to the exact ground state now:
- P1: 0.094 (was 0.513).
- P2: 0.784 (was 3.488).
- P3: 9.648. This is still worse than Week60's 7.061.

## 6. Why the seeded version works better

1. **It explores more of the Clifford landscape.**
   - The GA landscape is rugged and discrete, so each seeded GA converges to its own local optimum.
   - Eight independent GAs give the best of eight optima instead of one optimum found eight times.
   - Evidence: in a 200-generation P1 probe, GA 2 found -2.549 while GA 0 found -2.504. With 8 GAs at 2000 generations the best reached -2.935.
   - A better Clifford point means a better COBYLA starting basin, which is what decides the final energy (§4.4).
2. **The candidate pool is genuinely diverse.**
   - Before, there were 1–16 distinct points. Now there are 123 to 3,143 distinct *states* per problem.
   - The chosen starts differ in 19–209 gate angles, and they come from different GAs.
3. **Starts are no longer wasted on copies.** Merging by state removes the tied-energy duplicates that made Week91's three starts finish within 0.03 of each other.

**What the data does *not* show yet:**
- **The diverse extra starts haven't won.**
  - In all three problems the kept run was start 0, the global best point. The improvement comes from (1), independent searches, not from the extra starts.
  - The other starts began from noticeably worse points: the 0.25 window is permissive, and on P2 they started at QUBO about 8.2 vs 5.6. They finished about where they started.
  - On P3, start 2 came close (12.515 vs 12.373).
- **P3 still trails Week60** (12.373 vs 9.786). No search found a Clifford point as good as Week60's (QUBO 9.87).
- **The comparison isn't budget-matched.** Week93–95 used 1000 iterations against 10000 before, and P2 and P3 used all 1000. The energies may still improve.
- **P2's plan quality is limited by the QUBO**, not by initialization (§4.5). Its optimal ratio stays at about 0: 99.99% of samples decode to cost 465.

## 7. Possible next steps
- **Implement the paper's selection strategies** (fixed-interval and K-GAPS, with circular embedding and gradient-norm filter) next to max–min Hamming. Compare all three on the same seeded pool.
- **Tighten `--energy_window`** (e.g. 0.05–0.10). Diverse starts would then also be competitive starting points.
- **Larger search effort:** more independent GAs or several seeds (`--seed`), so P3 can reach Week60-quality points.
- **Run with matched budgets:** the same iteration budget for single-start and multi-start, and more trials.
- **Fix the QUBO penalty** (`problem-formulation.md` §3) before drawing conclusions about P1/P2 plan quality.
