# How the join-order problem is turned into a QAOA problem

This file explains, in plain terms, how we turn "pick the best join order" into something QAOA can solve.
It covers what we had before, what was wrong with it, and what we changed.
Keep it updated whenever the formulation changes or an experiment tests it. Code changes also go in `CHANGELOG.md`.

---

## 1. The idea in one paragraph

QAOA cannot "search for the cheapest join order" directly. It can only find bitstrings with **low energy**.
So we write an energy formula over bits with two goals:
- every bitstring that is **not a real join order** gets a **penalty**, so its energy is high;
- among real join orders, **cheaper plans get lower energy**.

If both goals hold, the lowest-energy bitstring is the best join order, and QAOA, by looking for low energy, finds good plans.
If either goal fails, QAOA can be doing its job perfectly and still return a bad plan.

**Formula vs Hamiltonian.** The energy formula is called a QUBO. The code (`qubo.to_ising()`) turns it into a Hamiltonian, which is the same formula rewritten for qubits. That conversion is exact and was never the problem. Everything below is about the formula itself.

## 2. Our test problems

| | Tables (rows in each) | Join conditions (selectivity) | Best plan's cost |
|---|---|---|---|
| P1 | 10, 15, 20 | 0–1 (0.1), 1–2 (0.1) | 15 |
| P2 | 10, 15, 20, 30 | 0–1 (0.1), 2–3 (0.1) | 315 |
| P3 | 10, 15, 20, 30 | 0–1 (0.1), 1–2 (0.2), 2–3 (0.3), 0–2 (0.4), 0–3 (0.5), 1–2 again (0.6) | 29.4 |

A plan's **cost** is the total size of the intermediate results. Example for P2 with order 0, 1, 2, 3:
- joining 0 and 1 gives 10 × 15 × 0.1 = **15** rows;
- adding table 2 gives 15 × 20 = **300** rows;
- so the cost is 15 + 300 = **315**. The final join always contains every table, so it is the same for every plan and isn't counted.

## 3. What we had before (the "Q2O" formulation, built for digital annealers)

### The bits
- One bit per **(table, join step)**: "is this table in the result after this join step?" For 4 tables that is 4 × 2 = 8 bits.
- One extra bit per **(join condition, join step)**: "is this join condition applied at this step?" For P3, with 6 conditions, that is 12 more bits.

### The energy
- **Penalty A:** each join step must contain the right number of tables (2 after the first join, 3 after the second, and so on).
- **Penalty B:** once a table is in, it stays in.
- **Penalty C:** a join condition may only be "on" if both of its tables are in.
- **Cost:** for each join step, take the log of the result size and **square it**. Logs turn the multiplications into additions.
- All penalties are multiplied by a weight λ, which was set to **the number of join steps** (1 for P1, 2 for P2 and P3).

## 4. What was wrong with it

### Problem 1: the penalty was too weak, so the lowest energy belonged to an invalid bitstring
Real-plan energies were ranked correctly; the cheapest plan had the lowest energy among real plans. But a **fake plan** that breaks a rule could get an even lower energy, because breaking a rule cost only λ = 2 while saving more than that.

**P2 example** (all logs are base 10):

| Bitstring | What it means | Energy |
|---|---|---|
| Best real plan | step 1 = {0,1}, step 2 = {0,1,2} | 1.18² + 2.48² = **7.52** |
| Fake plan | step 1 = {0,1}, step 2 = {0,1}: table 2 forgotten, so Penalty A = 1 | 2 × 1 + 1.18² + 1.18² = **4.77** |

The fake plan wins. When decoded, it turns into the order 1, 0, 3, 2, which costs **465**. That is exactly what we saw: 99.99% of P2 samples had cost 465.
For the real plan to win, λ needed to be above 4.75. It was 2.

**P1 example.** The lowest energies belonged to bitstrings that switched on a join condition whose tables weren't both present, which Penalty C allows at the price of only 1. One of them decodes to the cost-**30** plan. That explains P1's 50/50 split between 15 and 30.

### Problem 2: squaring the cost rewards "making the result look small"
With a squared cost, anything that pushes the log-size toward 0 lowers the energy, including cheating: dropping a table, or switching on a join condition that doesn't apply. And the bigger the join, the more one cheat saves:
- squared cost: dropping a table of log-size ℓ from a join of log-size L saves 2·L·ℓ − ℓ². In P2 that is **4.75**;
- plain (unsquared) cost: it saves only ℓ. In P2 that is **1.30**.

For a 10-table query with tables of about 100,000 rows, the squared version would need a penalty around **175**, compared with about **5** for the plain one.

### Problem 3: too many qubits
The join-condition bits add (number of conditions) × (number of join steps) qubits: 2, 4 and 12 extra for P1, P2 and P3. They exist only because the squared cost can't be written without them.

### Problem 4: the cost checker disagreed with the energy on P3
P3 lists the pair 1–2 twice. That means two separate conditions between the same tables, for example `A.x = B.x AND A.y = B.y`, so both selectivities should apply: 0.2 × 0.6. The energy formula applied both, but the cost checker (`Postprocessing.py`) applied only the first. So the checker said P3's best cost was 39, while the true best is 29.4. It was the same plan either way.

### What was fine
- Penalties A and B together are exactly right. A bitstring passes both if and only if it is a real join order. Nothing is missing and nothing is extra.
- Turning the formula into the Hamiltonian, and the QAOA circuit built from it, are correct. They faithfully encode the formula; the formula was the problem.

## 5. What we changed (the "qaoa" formulation)

| | Before ("q2o") | Now ("qaoa") |
|---|---|---|
| Bits | tables × steps **+ conditions × steps** | tables × steps only |
| Qubits (P1 / P2 / P3) | 5 / 12 / 20 | **3 / 8 / 8** |
| How a join condition is counted | its own bit, kept honest by Penalty C | "table a is in **and** table b is in", written as the product of their two bits, so it **cannot cheat** |
| Cost per join step | (log size)² | **log size** (not squared) |
| Penalty weight λ | number of join steps (1, 2, 2) | **1.1 × the largest log table size** (1.43, 1.63, 1.63), computed from the data |
| Penalties A and B | yes | yes, unchanged |
| Penalty C | yes | **gone**: there are no condition bits left to police |
| Repeated pair (P3 1–2) | energy: both applied; checker: first only | both applied in the energy **and** in the checker |

### Why each change helps
- **Removing the condition bits** saves qubits, makes illegal conditions impossible, and removes a whole penalty.
- **Not squaring** removes the reward for cheating. It still ranks the plans just as well; in all three problems the cheapest plan stays cheapest. With a single join step, the energy of a real plan is exactly log(cost): P1's plans get 1.18 = log 15, 1.48 = log 30 and 2.30 = log 200.
- **λ from the data.** Cheating by dropping a table saves at most that table's log size, so λ only has to beat the largest one. 1.1 × the largest is just enough. Keeping λ small matters for QAOA: a big penalty stretches the energy range, and the small difference between the best and second-best plan becomes hard to tell apart.

### Checked (exact energies of every bitstring, no QAOA run)

| | λ | Lowest-energy bitstring | Its decoded cost | Best cost |
|---|---|---|---|---|
| P1 | 1.43 | a real plan | 15 | 15 |
| P2 | 1.63 | a real plan | 315 | 315 |
| P3 | 1.63 | a real plan | 29 (29.4, stored as a whole number) | 29.4 |

### Expected effect on QAOA (estimates, not yet measured)

| | Two-qubit gates per layer (before → now) | Share of the starting state that is a real plan (before → now) |
|---|---|---|
| P1 | 10 → 3 | 15.6% → 37.5% |
| P2 | 34 → 16 | 0.78% → 4.7% |
| P3 | 94 → 16 | 0.024% → 4.7% |

### Known limit
The λ rule is argued only for the "forgot a table" kind of cheat. It is not proven for the "swapped a table between steps" kind. It holds on P1–P3; `base/test_qubo_formulation.py` checks this by brute force. If a bigger problem ever ends up with a fake plan at the lowest energy, switch to the guaranteed-safe weight:

  λ = (energy of any real plan) − (number of join steps × sum of the negative log selectivities) + 1

The safe weight is larger, so the best-vs-second-best difference gets harder to see. A comment in `QUBOGenerator.py` points to this.

## 6. What about the "Ready to Leap" formulation?
It was built for gate-based machines, but it isn't a better fit for QAOA.
- It approximates each result size with "is the size above threshold 1? above threshold 2? …" bits, plus extra helper bits to make the inequalities work. That needs many more qubits; even small problems run past our 23-qubit limit.
- Plans whose sizes fall between the same two thresholds get the same energy, so QAOA can't tell them apart.
- It still depends on a penalty weight, with the same risk as Problem 1.

(This description is from memory of the paper; re-check it before citing.)

## 7. How to use it
- `base/config.py`: `"qubo-formulation": "qaoa"` (the default) or `"q2o"` (the old one). `IBMQExperiments.py`, `spiq_initialization.py` and `postprocess_results.py` all read this setting.
- SPIQ output files now end in `_<formulation>`, e.g. `spiq_initial_point_input1_reps2_4rel_2pred_qaoa.json`, and record the formulation inside the file. `IBMQExperiments.py` refuses to load a SPIQ file made for the other formulation. Older files, which don't record one, count as `"q2o"`.
- To re-process **old** results with `postprocess_results.py`, set the config to `"q2o"` first.
- Old CSVs (Week93–95) were scored with the old checker, so P3's target in `graphs/seeded-multi-spiq.rmd` stays at **39** for them. New P3 runs score the best plan as **29**.
- The decoder needed no change; it already reads only the table bits.

## 8. To do
- [x] Run `python3 test_qubo_formulation.py` in the container (from `base/`). It passes.
- [x] Random-start QAOA with the new formulation (Week96–98). Results are in the log below.
- [x] SPIQ-started QAOA with the new formulation (Week102–104, same settings as Week93–95). Results are in the log below.
- [ ] P2 still splits 50/50 between the best plan (315) and the second-best (465). Ideas: more SPIQ starts, or a slightly stronger cost term so the two plans are further apart in energy.
- [ ] Later, only if needed: an exact-cost version, or special QAOA mixers that never leave the set of real plans (these need no penalty, but cost more qubits).

## 9. Experiment log

Newest first.

| Date | Formulation | Problem | Result | Where |
|---|---|---|---|---|
| 2026-10-13 | qaoa, **single-start SPIQ** (one GA, seed 0, 2000 generations, one QAOA run) (Week105–107) | P1–P3 | Share at the best plan: **P1 1.000, P2 0.000, P3 1.000**. See "Single-start SPIQ" below. | `outputs/spiq/Week105–107` (+ `energy/`) |
| 2026-10-12 | qaoa, **multi-start SPIQ**, same settings as Week93–95 (Week102–104) | P1–P3 | Share at the best plan: **P1 1.000, P2 0.503, P3 1.000** (old formulation: 0.507, 0.0001, 0.126). See "Multi-start SPIQ" below. | `outputs/multi-spiq/Week102–104` (+ `energy/`) |
| 2026-10-12 | q2o, random start, same settings (Week99–101) | P1–P3 | The like-for-like old-formulation partner runs. See "Old vs new formulation" below. | `outputs/uninitialized/Week99–101` (+ `energy/`) |
| 2026-10-12 | qaoa, **random start**, COBYLA, reps 2, max 1000 iterations | P1–P3 | See the table below. COBYLA stopped early (123–137 evaluations) far above the lowest possible energy, so a random start with only 4 angles does not reach the good plans, even though the formula now puts them at the bottom. | `outputs/uninitialized/Week96–98` (+ `energy/`) |
| 2026-10-12 | qaoa (λ = 1.1 × largest log size) | P1–P3 | Exact energies: the lowest-energy bitstring is a real plan with the best cost in all three (15, 315, 29). | analysis only |
| 2026-10-07 | q2o vs qaoa, several λ | P1–P3 | Smallest λ that works: q2o 1.35 / 4.75 / 1.16, qaoa 0.29 / 1.30 / 0.29. A bigger λ shrinks the visible best-vs-second-best difference roughly as 1/λ. | analysis only |
| 2026-10-07 | q2o, λ = number of steps | P1–P3 | Exact energies: in P1 and P2 a fake plan has the lowest energy and decodes to cost 15/30 (P1) and 465 (P2). | analysis only |
| 2026-09-30 | q2o, λ = number of steps | P1–P3 | Seeded multi-start SPIQ, share of samples at the best plan: P1 0.507, P2 0.0001 (99.99% at 465), P3 0.126. | `outputs/multi-spiq/Week93–95` |

### Random-start runs with the new formulation (2026-10-12)

"Share at best plan" is the fraction of the 10,240 samples whose decoded plan has the best cost. "Plain" decoding reads the order straight from the bits; "fallback" decoding repairs the order to avoid cross joins.

| | Lowest possible energy | Energy reached | Share at best plan: first step (plain / fallback) | Share at best plan: end (plain / fallback) | Most common plan cost at the end (plain) |
|---|---|---|---|---|---|
| P1 (Week96) | 1.176 | 1.929 | 0.013 / 0.114 | **0.220 / 0.252** | 30 (63%) |
| P2 (Week97) | 3.653 | 8.938 | 0.013 / 0.066 | **0.018 / 0.055** | 960 (22%) |
| P3 (Week98) | 2.334 | 5.507 | 0.008 / 0.125 | **0.036 / 0.189** | 504 (16%) |

What this tells us:
- **P2's "465 trap" is gone.** Week94 put 99.99% of samples on cost 465; Week97's samples are spread across many plans. **P1 still leans to the second-best plan** (63% at cost 30). In the new formula that plan is a real plan with the second-lowest energy (1.477 vs 1.176), not a fake one, so a stronger optimizer or start should move samples to 15.
- **A random start is too weak to find the best plan.** The energy reached is still far above the lowest possible, so most samples are invalid bitstrings or poor plans. This is a limit of random-start QAOA with 4 angles, not of the formula.
- **For comparison**, the old formulation's random-start P2 run (Week74/Week84, up to 10,000 iterations) got 0.021 plain / 0.099 fallback, which is similar. Random starts were weak under both formulations.
- **Next:** SPIQ-started runs with the new formulation. Week93–95 were SPIQ-started, so that is the like-for-like comparison.

### Old vs new formulation, both with a random start (2026-10-12)

To compare fairly, the old formulation was re-run with the same code, settings and starting angles (all 0.5) as Week96–98: Week99 (P1), Week100 (P2) and Week101 (P3). The only difference is `qubo-formulation`.

**Energies.** The two formulations use different energy scales, so the raw numbers can't be compared directly. The last column fixes that: it shows how much of the distance from the starting energy down to the lowest possible energy the optimizer covered (0 = no progress, 1 = reached the bottom).

| Workload | Formulation | Lowest possible | Start energy | Final energy | Best energy seen | Share of the way to the bottom |
|---|---|---|---|---|---|---|
| P1 | old (q2o), Week99 | 1.031 | 5.083 | 2.733 | 2.710 | 0.59 |
| P1 | **new (qaoa), Week96** | 1.176 | 4.364 | 1.935 | 1.929 | **0.76** |
| P2 | old (q2o), Week100 | 4.766 | 24.684 | 19.404 | 19.269 | 0.27 |
| P2 | **new (qaoa), Week97** | 3.653 | 13.254 | 8.961 | 8.938 | **0.45** |
| P3 | old (q2o), Week101 | 2.725 | 30.606 | 22.852 | 22.758 | 0.28 |
| P3 | **new (qaoa), Week98** | 2.334 | 12.615 | 5.593 | 5.507 | **0.69** |

**Optimal ratio** (share of samples whose plan has the best cost):

| Workload | Formulation | Start: plain | Start: fallback | End: plain | End: fallback | Most common plan at the end (plain) |
|---|---|---|---|---|---|---|
| P1 (best 15) | old (q2o) | 0.040 | 0.198 | 0.129 | **0.470** | 30 (55%) |
| P1 (best 15) | new (qaoa) | 0.013 | 0.114 | **0.220** | 0.252 | 30 (63%) |
| P2 (best 315) | old (q2o) | 0.010 | 0.060 | 0.018 | **0.101** | 900 (25%) |
| P2 (best 315) | new (qaoa) | 0.013 | 0.066 | 0.018 | 0.055 | 960 (22%) |
| P3 (best 29) | old (q2o) | 0.018 | 0.160 | 0.022 | 0.150 | 504 (22%) |
| P3 (best 29) | new (qaoa) | 0.008 | 0.125 | **0.036** | **0.189** | 504 (16%) |

What this shows:
- **The optimizer gets much further with the new formulation:** 0.76 vs 0.59, 0.45 vs 0.27 and 0.69 vs 0.28 of the way to the bottom. A smaller penalty weight and fewer qubits make the energy landscape easier for QAOA.
- **Plain decoding gets better or stays level:** P1 0.129 → 0.220, P2 0.018 → 0.018, P3 0.022 → 0.036.
- **Fallback decoding is mixed:** P3 improves (0.150 → 0.189), while P1 (0.470 → 0.252) and P2 (0.101 → 0.055) drop. Under the old formulation many samples are fake plans, and the fallback repair often turns those into good plans by luck. With the new formulation more samples are real but second-best plans, which the repair leaves alone.
- **Neither random start gets most samples onto the best plan.** With only 4 angles and COBYLA stopping after about 120 evaluations, random-start QAOA is weak under both formulations. The bigger test is still SPIQ-started runs.

### Multi-start SPIQ with the new formulation (2026-10-12)

Same settings as Week93–95 (8 independent GA searches, 2000 generations, seed 0, energy window 0.25, 10 candidates, 3 QAOA starts, COBYLA up to 1000 evaluations, reps 2). Only the formulation differs. Week102 = P1, Week103 = P2, Week104 = P3.

**Optimal ratio** (share of the 10,240 samples at the best plan; plain and fallback decoding gave the same numbers in every run):

| Workload | Old formulation (Week93–95): start / end | **New formulation (Week102–104): start / end** | Rest of the samples (new) |
|---|---|---|---|
| P1 (best 15) | 0.502 / 0.507 | **1.000 / 1.000** | none |
| P2 (best 315) | 0.000 / 0.0001 | **0.503 / 0.503** | 465 (49.6%), 600 (3 samples) |
| P3 (best 29) | 0.121 / 0.126 | **1.000 / 1.000** | none |

**Energies**:

| Workload | Lowest possible | SPIQ start (winning start) | Best reached | Still above the bottom | Evaluations |
|---|---|---|---|---|---|
| P1 | 1.176 | 1.176 | 1.176 | **0** | 284 |
| P2 | 3.653 | 3.741 | 3.739 | 0.085 | 1000 |
| P3 | 2.334 | 2.334 | 2.334 | **0** | 991 |

Old formulation, for comparison (its own scale): it ended 0.094 (P1), 0.784 (P2) and 9.65 (P3) above its lowest possible energy.

What this shows:
- **For P1 and P3 the SPIQ search already finds the exact answer.** The best Clifford starting point *is* the ground state, which is the best plan, so every sample is the best plan from the first step on. Under the old formulation the same search could only reach fake or mixed states, because the ground state was a fake plan (P1) or too hard to reach with 20 qubits (P3).
- **P2 goes from almost 0% to 50% at the best plan.** The remaining 50% is the second-best plan (cost 465), which is now a real plan with an energy only 0.18 above the best (≈3.83 vs 3.65). The SPIQ start is an even mix of the two, and COBYLA could not shift the balance. The old formulation's fake 465 state (energy 4.77, below every real plan) is gone.
- **The winning start was start0 (the best SPIQ point) in all three.** The other two starts ended higher (P1 1.321 / 1.188, P2 4.545 / 4.984, P3 3.808 / 2.884).
- **Much faster.** Fewer qubits mean fewer SPIQ angles (18 / 64 / 64 instead of 40 / 116 / 268): the whole pipeline took about 0.9 h (P1) and 1.7 h (P2, P3), compared with 3–6.7 h for Week93–95.
- **Random start vs SPIQ (same new formulation):** end share at the best plan 0.22 → 1.00 (P1), 0.018 → 0.503 (P2), 0.036 → 1.00 (P3). The starting point matters more than anything else here.

Plots: `graphs/formulation.rmd` sections 4, 5 and 7.

### Single-start SPIQ with the new formulation (2026-10-13)

The original SPIQ: **one** GA search (seed 0, 2000 generations), **one** starting point, **one** QAOA run (COBYLA up to 1000 evaluations, reps 2). Week105 = P1, Week106 = P2, Week107 = P3. Everything else is the same as Week102–104.

| Workload | Random (Week96–98): end | **Single-start SPIQ (Week105–107): start / end** | Multi-start SPIQ (Week102–104): end | Energy reached (single) | Lowest possible |
|---|---|---|---|---|---|
| P1 (best 15) | 0.220 | **1.000 / 1.000** | 1.000 | 1.176 | 1.176 |
| P2 (best 315) | 0.018 | **0.000 / 0.000** | 0.503 | 5.100 | 3.653 |
| P3 (best 29) | 0.036 | **1.000 / 1.000** | 1.000 | 2.334 | 2.334 |

(Plain and fallback decoding agree in every single-start run.)

What this shows:
- **P1 and P3: one search is enough.** The single GA finds the same starting point as multi-start, which is the exact ground state (the best plan). This is expected: multi-start's best point on these two also came from GA 0, which uses the same seed.
- **P2: one search is not enough.** The single GA's best point (energy 5.13) mixes plans with costs 465 (50%), 900 (25%) and 1350 (25%), and none with the best cost 315. COBYLA only lowered it to 5.10. Multi-start's best point came from a different GA (GA 7) and started at 3.74, already half on the best plan. So on P2 the extra independent searches are what make the difference.
- **Run time:** about 7 min (P1) and 13 min (P2, P3), compared with 0.9–1.7 h for multi-start.

Plots: `graphs/formulation.rmd` sections 6 and 7.2.
