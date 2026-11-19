# Results index

Which week folder holds which run. All runs use QAOA reps=2 and COBYLA with up to 10000 iterations.
"Params" is the number of optimised angles: 4 for random initialization (2·reps),
or one per gate of the relaxed circuit for SPIQ. "Qubits" is the bitstring length
in the readouts. Energies are on the QUBO scale unless noted.

Problems (`--input_idx`, current definitions since commit `ce7efac6`, 2026-09-23):

| Problem | input_idx | Shape | Qubits | SPIQ params | Exact ground state (QUBO) |
|---|---|---|---|---|---|
| P1 | 0 | 3 relations, 2 predicates | 5 | 40 | 1.031 |
| P2 | 1 | 4 relations, 2 predicates | 12 | 116 | 4.766 |
| P3 | 2 | 4 relations, 6 predicates | 20 | 268 | 2.725 |
| P4 | 3 | 5 relations, 5 predicates | 15 (new "qaoa" formulation only) | 140 | 4.908 (qaoa) |
| P5 | 4 | 6 relations, 7 predicates | 24 (new "qaoa" formulation only) | 252 | 8.340 (qaoa) |

Older runs are all filed under `input0` whatever the problem, so they're identified here by qubit and parameter count.

## Findings: formulation experiments (Week96 on)

What each run showed, newest first. This section was moved here from `docs/problem-formulation.md`.

Newest first.

| Date | Formulation | Problem | Result | Where |
|---|---|---|---|---|
| 2026-11-18 | qaoa, single-start SPIQ (the Week108/109 starts), **10000 evaluations** instead of 1000, COBYLA (Week117 P4, Week118 P5) and NFT (Week119 P4, Week120 P5) | P4, P5 | **NFT moves on both; COBYLA moves on neither.** P4 NFT: 7.40 → **6.195** (48% of the gap to 4.908); share at the best plan with fallback 0.252 → **0.491**, raw still 0. P5 NFT: 17.59 → **15.661** (21% of the gap to 8.340) and still improving at 10000; the best plan 1605 appears for the first time (3 of 10240 samples, fallback only). COBYLA stops on its own (P4 after 3843 evaluations at 7.387, P5 after 6820 at 17.461). See "P4 and P5 with 10000 evaluations" below. | `outputs/long/Week117–120` (+ `energy/`) |
| 2026-10-27 | qaoa, single-start SPIQ (the Week105–109 starting points), **NFT optimizer** instead of COBYLA (Week112–116) | P1–P5 | Same as COBYLA everywhere except P2: final energy **P2 4.860 vs 5.100** (exact 3.653), but the share at the best plan is still 0. P1/P3 stay at the ground state (share 1.0). P4/P5 are unchanged (7.390 vs 7.380, 17.504 vs 17.482). See "NFT instead of COBYLA" below. | `outputs/nft/Week112–116` (+ `energy/`) |
| 2026-10-21 | **q2o vs qaoa, single-start SPIQ starting point only** (no QAOA; q2o needs 30 / 52 qubits) (Week110–111 for q2o, the Week108–109 points for qaoa) | P4, P5 | Share of samples that are valid plans: **P4 qaoa 0.247 vs q2o 0.003; P5 qaoa 0.065 vs q2o 0.000**. With fallback decoding, share at the best plan: P4 0.256 vs 0.188, P5 0.000 vs 0.047. See "Old vs new formulation on P4/P5" below. | `spiq_init_outputs/single_Week108–111` |
| 2026-10-20 | qaoa, single-start SPIQ, same settings as Week105–107 (Week108–109) | **P4 (5 tables, 15 qubits), P5 (6 tables, 24 qubits)** | Share at the best plan: **P4 0.000 raw / 0.252 with fallback, P5 0.000**. See "Larger problems" below. | `outputs/spiq/Week108–109` (+ `energy/`) |
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

### Larger problems: 5 and 6 tables, single-start SPIQ (2026-10-20)

The same settings as Week105–107. Week108 = P4 (5 tables, 15 qubits, 140 angles) and Week109 = P5 (6 tables, 24 qubits, 252 angles). The self-check (`test_qubo_formulation.py`) confirms that the lowest-energy bitstring of each is a real plan with the best cost (165 and 1605).

| Workload | Qubits | Share at best plan (raw / fallback) | Energy: start → end | Lowest possible | Most common costs (raw decode) | Run time |
|---|---|---|---|---|---|---|
| P4 (best 165) | 15 | 0.000 / **0.252** | 7.449 → 7.380 | 4.908 | 330 (50%), 2700 (25%), 7200 (25%) | 24 min |
| P5 (best 1605) | 24 | 0.000 / 0.000 | 17.558 → 17.482 | 8.340 | 8500–32750, spread out; cheapest seen 7890 (fallback, 6%) | 75 min |

What this shows:
- **The single GA start is far from the ground state on both.** Unlike P1 and P3, the GA's best Clifford point is not the best plan. COBYLA then barely moves (−0.07 on each), and the first-iteration readout is almost the same as the final one.
- **P4 is close.** Half the samples are on cost 330, the second-best order (swap tables 2 and 3). With fallback decoding a quarter reach the best plan, 165.
- **P5 does not get near the best plan.** It is 9.1 above the lowest energy. With 252 angles and 1000 evaluations, COBYLA has fewer than four evaluations per angle.
- Next to try: multi-start SPIQ (it fixed P2), or more COBYLA evaluations.

Plots: `graphs/formulation.rmd` section 8.

### Old vs new formulation on P4/P5: SPIQ starting points only (2026-10-21)

With the old formulation, P4 and P5 need 30 and 52 qubits, too many to simulate QAOA. So this compares only what single-start SPIQ (one GA, seed 0, 2000 generations, reps 2) gives as the starting state. That state is a Clifford state, so stim can sample it at any size. `base/spiq_sample.py` takes 10240 samples and decodes them like a QAOA readout. The new-formulation points are the ones QAOA started from in Week108/109. The old-formulation points are Week110 (P4) and Week111 (P5).

| Workload | Formulation | Qubits | Angles | Valid plans | Best plan (raw / fallback) | Median cost (raw / fallback) | Distinct states in 10240 samples | SPIQ run time |
|---|---|---|---|---|---|---|---|---|
| P4 (best 165) | **new** | 15 | 140 | **0.247** | 0.000 / **0.256** | 330 / 330 | 4 | 18 min |
| P4 (best 165) | old | 30 | 410 | 0.003 | 0.004 / 0.188 | 5175 / 2700 | 10154 | 76 min |
| P5 (best 1605) | **new** | 24 | 252 | **0.065** | 0.000 / 0.000 | 19250 / 11625 | 16 | 40 min |
| P5 (best 1605) | old | 52 | 868 | 0.000 | 0.001 / 0.047 | 20550 / 7890 | 10240 | 117 min |
| *uniformly random bits* | – | – | – | – | P4 0.004 / 0.145, P5 0.001 / 0.023 | – | – | – |

What this shows:
- **The old-formulation starting points are close to random guessing.** Almost every sample is a different bitstring, almost none are valid plans, and the share at the best plan is only a little above the uniform-random baseline (P4 0.188 vs 0.145, P5 0.047 vs 0.023). What does land on the best plan comes from the fallback repair, not from SPIQ.
- **The new-formulation starting points are concentrated.** Only 4 (P4) or 16 (P5) distinct states. On P4 a quarter of the samples are valid plans and a quarter decode to the best plan.
- **On P5, neither start contains the best plan.** The new start sits on a few bad plans: it beats the old start on valid plans, but is worse on share-at-best and median fallback cost. This matches the Week109 QAOA result ("Larger problems" above).
- **Size:** the old formulation needs 2–3.4× the qubits and angles, and the SPIQ search took 3–4× longer.

Plots: `graphs/formulation.rmd` section 9.

### NFT instead of COBYLA, same SPIQ start (2026-10-27)

Week112–116 restart QAOA from exactly the single-start SPIQ points of Week105–109. The only change is the optimizer: NFT (`--optimizer 3`), with the same budget of 1000 energy evaluations and reps 2. ("Start" is the first energy each optimizer measured, which is why it differs slightly between the two.) NFT tunes one angle at a time. It fits the energy as a sine curve in that angle and jumps to the curve's minimum. That fit is exact for SPIQ's circuit, where each angle drives one gate. So NFT should make bigger, better-aimed moves than COBYLA.

| Problem | Exact ground | Start | COBYLA final | NFT final | Share at best plan (raw / fallback), COBYLA → NFT |
|---|---|---|---|---|---|
| P1 | 1.176 | 1.176 | 1.176 | 1.176 | 1.0 / 1.0 → 1.0 / 1.0 |
| P2 | 3.653 | 5.13 | 5.100 | **4.860** | 0 / 0 → 0 / 0.0001 |
| P3 | 2.334 | 2.334 | 2.334 | 2.334 | 1.0 / 1.0 → 1.0 / 1.0 |
| P4 | 4.908 | 7.42–7.45 | 7.380 | 7.390 | 0 / 0.252 → 0 / 0.252 |
| P5 | 8.340 | 17.56–17.57 | 17.482 | 17.504 | 0 / 0 → 0 / 0 |

What this shows:
- **NFT works better than COBYLA only on P2.** It closes 18% of the gap from the start to the ground state, against COBYLA's 2%. That is not enough to change the readout: the samples move between the same bad plans (465, 900, 960), and the best plan (315) shows up once in 10240 samples.
- **On P4 and P5 both optimizers barely move** (1–3% of the gap) within 1000 evaluations. With 10000, NFT does move on P4; see "P4 and P5 with 10000 evaluations" below.
- **On P1 and P3 SPIQ already lands on the answer**, so there is nothing left to optimize.

- **On P2, NFT was still improving when the budget ran out:** its best energy dropped mainly in the last 250 evaluations. A larger budget is the obvious next test for P2.

Plots: `graphs/nft.rmd`, with energy-over-iteration plots of NFT vs COBYLA and first-vs-final optimal-ratio tables. Also `graphs/formulation.rmd` section 10.

### P4 and P5 with 10000 evaluations (2026-11-18)

Week117 (COBYLA) and Week119 (NFT) restart from the same Week108 SPIQ point as Week108/115. The only change is the budget: 10000 evaluations instead of 1000.

| Run | Evaluations used | Best energy after 1k / 3k / 5k / end | Gap closed (exact 4.908) | Share at best plan, raw / fallback | Samples |
|---|---|---|---|---|---|
| COBYLA, 1000 (Week108) | 1000 | 7.380 | 3% | 0 / 0.252 | 330 50%, 2700 25%, 7200 25% |
| **COBYLA, 10000 (Week117)** | **3843** (stopped on its own) | 7.388 / 7.387 / – / **7.387** | 1% | 0 / 0.250 | the same three plans |
| NFT, 1000 (Week115) | 1000 | 7.390 | 0.4% | 0 / 0.252 | 330 / 2700 / 7200 |
| **NFT, 10000 (Week119)** | 10000 | 7.396 / 7.285 / 6.203 / **6.195** | **48%** | **0 / 0.491** | two bitstrings, ~50% each (below) |

What this shows:
- **COBYLA is stuck, not short of budget.** Its trust region shrinks to the minimum size, so it stops after 3843 evaluations. Its best energy (7.387 vs 7.380) is the same within shot noise.
- **NFT escapes the plateau, but only after about 3000 evaluations.** Its best energy is flat until evaluation ~3100. It then falls in steps to 6.34 by evaluation 4174, and barely changes after that (6.195 at 10000). With 140 angles, NFT needs about 21 full passes over all angles before the first real improvement. That is why 1000 evaluations (about 7 passes) showed nothing.
- **The final state is two bitstrings, about 50% each:**
  - `111111001011000`: a valid plan with cost 330, the second-best order (tables 2 and 3 swapped).
  - `101111011011000`: invalid. Table 0 is in the first step, leaves in the second step, and returns in the third (a penalty-B violation). It is two bit flips from the best plan's bitstring (in step 2, table 3 is in place of table 0), and the fallback repairs it to 165.

  So the optimizer is moving toward the best plan, but through a state that breaks the "stay joined" rule. The raw share at the best plan is still 0.

Why the best plan is still missed (energies of each state, share of each plan at the start and the end, possible causes): `docs/bottleneck.md`.

**P5 (Week118 COBYLA, Week120 NFT)**, from the Week109 start, best plan 1605, exact energy 8.340:

| Run | Evaluations used | Best energy after 1k / 2k / 5k / 9k / end | Gap closed | Distinct bitstrings, start → end | Samples with fallback cost ≤ 8115 | Median fallback cost | Best plan 1605 (raw / fallback) |
|---|---|---|---|---|---|---|---|
| COBYLA, 1000 (Week109) | 1000 | 17.482 | 1% | – | – | – | 0 / 0 |
| **COBYLA, 10000 (Week118)** | **6820** (stopped on its own) | 17.489 / 17.484 / 17.461 / – / **17.461** | 1% | 16 → 21 | 6.3% → 6.5% | 10600 → 10600 | 0 / 0 |
| NFT, 1000 (Week116) | 1000 | 17.504 | 1% | – | – | – | 0 / 0 |
| **NFT, 10000 (Week120)** | 10000 | 17.522 / 16.714 / 16.463 / 16.168 / **15.661** | **21%** | 16 → 76 | 6.2% → **24.7%** | 10600 → **9015** | 0 / **3 samples** |

What this shows:
- **The pattern is the same as P4.** COBYLA stops on its own with nothing gained. NFT is flat for about 1700 evaluations, then drops in steps at evaluations ~1700–1900 and again after ~8000.
- **NFT on P5 was still improving when the budget ran out.** Its best energy fell from 16.168 to 15.661 in the last 1000 evaluations. A larger budget would probably go further.
- **The start is 16 bitstrings at about 6% each**, a Clifford state like P4's. NFT moves the weight onto about 6 of them and their neighbours, at ~12.5% each, all with cheaper plans: a quarter of the samples now repair to a plan costing at most 8115.
- **The best plan appears for the first time** (3 of 10240 samples, only after fallback repair), but it is still far from the dominant states. The energy (15.66) is also still far above the minimum (8.34).
- **Run time:** about 6 h (COBYLA) and 7.6 h (NFT) with four runs in parallel, much less than the ~13 s per evaluation measured early on. The energy step is cheap while the samples stay on few distinct bitstrings.

Plots: not yet; `graphs/nft.rmd` covers the 1000-evaluation runs.


## Multi-start runs (`outputs/multi-spiq/energy/WeekNN` = energy logs, `outputs/multi-spiq/WeekNN` = postprocessed readouts)

| Week | Problem | Method | Notes |
|---|---|---|---|
| Week90 | P1 | Single-start SPIQ | 835 evals, min energy 1.544 |
| Week91 | P2 | Multi-start SPIQ: 10 candidates exported, 3 starts, winner start0 | min 8.254. Per-start logs are `_start{0,1,2}.csv`. The readouts' first line is a `#` run note |
| Week92 | P3 | Multi-start SPIQ: 10 candidates exported, 3 starts, winner start1 | min 12.825 (the starts reached 13.52 / 12.82 / 13.20). The readouts' first line is a `#` run note |
| Week93 | P1 | **Diverse** multi-start SPIQ, **1000 iterations** | min **1.125** (exact 1.031). SPIQ best Ising -2.935. Starts reached 1.125 / 1.662 / 1.544; winner start0 |
| Week94 | P2 | **Diverse** multi-start SPIQ, **1000 iterations** | min **5.550** (exact 4.766). SPIQ best Ising -14.918. Starts reached 5.550 / 8.166 / 8.280; winner start0 |
| Week95 | P3 | **Diverse** multi-start SPIQ, **1000 iterations** | min **12.373** (exact 2.725). SPIQ best Ising -13.372. Starts reached 12.373 / 14.923 / 12.515; winner start0 |
| Week102 | P1 | Diverse multi-start SPIQ, **"qaoa" formulation** (3 qubits, 18 params), Week93–95 settings | min **1.176 = exact**. SPIQ best Ising -1.494. Pool 2687 k-vectors / 17 distinct states / 6 in window, so only 6 candidates. Starts reached 1.176 / 1.321 / 1.188; winner start0 (284 evals). Optimal ratio 1.000 |
| Week103 | P2 | Same, "qaoa" (8 qubits, 64 params) | min **3.739** (exact 3.653). SPIQ best Ising -6.712. Pool 3291 / 241 distinct / 123 in window. Starts reached 3.739 / 4.545 / 4.984; winner start0. Optimal ratio 0.503 (rest at 465) |
| Week104 | P3 | Same, "qaoa" (8 qubits, 64 params) | min **2.334 = exact**. SPIQ best Ising -7.548. Pool 3392 / 177 distinct / 60 in window. Starts reached 2.334 / 3.808 / 2.884; winner start0 (991 evals). Optimal ratio 1.000 |

Week93–95 settings: 8 independent GAs (`--n_starts 8`), seed 0, `--n_gens 2000`,
`--energy_window 0.25`, `--n_candidates 10`, `--spiq_starts 3`, COBYLA with 1000
iterations, reps 2, trial 1. Their files are under `iterations_1000/…` with the name
`energy_per_iteration_1000_COBYLA_2_1*.csv`, not `iterations_10000`. SPIQ outputs
are in `spiq_init_outputs/diverse_WeekNN/`, and the run logs in `logs/diverse_WeekNN_inputN.log`.

Single-start SPIQ runs (`outputs/spiq/energy/WeekNN`, `outputs/spiq/WeekNN`), new "qaoa" formulation, one GA (`--n_starts 1 --n_proc 8 --seed 0 --n_gens 2000 --n_candidates 1`), `--spiq_starts 1`, COBYLA 1000 iterations, reps 2. SPIQ files in `spiq_init_outputs/single_WeekNN/`, logs in `logs/single_WeekNN_inputN.log`, response pickles in `energy/WeekNN/response_pickle_trial1_qaoa`:

| Week | Problem | Notes |
|---|---|---|
| Week105 | P1 | min **1.176 = exact** (284 evals). SPIQ Ising -1.494 (same point as Week102). Optimal ratio 1.000 |
| Week106 | P2 | min **5.100** (exact 3.653, 1000 evals). SPIQ Ising -5.329. Optimal ratio 0.000 (465 50%, 900 25%, 1350 25%) |
| Week107 | P3 | min **2.334 = exact** (994 evals). SPIQ Ising -7.548 (same point as Week104). Optimal ratio 1.000 |
| Week108 | P4 (5 tables, 15 qubits) | min **7.380** (exact 4.908, 1000 evals). SPIQ Ising -16.734. Optimal ratio 0.000 raw / 0.252 fallback (raw: 330 50%, 2700 25%, 7200 25%) |
| Week109 | P5 (6 tables, 24 qubits) | min **17.482** (exact 8.340, 1000 evals). SPIQ Ising -31.127. Optimal ratio 0.000 (no sample at cost 1605) |

SPIQ-only runs (no QAOA), old "q2o" formulation, same single-start SPIQ settings, started with `QUBO_FORMULATION=q2o bash logs/run_spiq_only.sh <idx> <week> <opt_cost>`. The starting point is sampled 10240 times with stim by `base/spiq_sample.py`. The files are in `spiq_init_outputs/single_WeekNN/` (JSON, pcirc QPY, `*_readout.csv`), and the logs in `logs/spiqonly_WeekNN_inputN.log`. The Week108/109 folders also hold a `*_qaoa_readout.csv` of their starting points, made the same way.

| Week | Problem | Notes |
|---|---|---|
| Week110 | P4, q2o (30 qubits, 410 angles) | SPIQ energy 47.57 (q2o scale; no exact ground state above 25 qubits). Valid plans 0.003, at best plan 0.004 raw / 0.188 fallback |
| Week111 | P5, q2o (52 qubits, 868 angles) | SPIQ energy 122.27 (q2o scale). Valid plans 0.000, at best plan 0.001 raw / 0.047 fallback |

QAOA with the **NFT** optimizer (`--optimizer 3`, 1000 evaluations, reps 2), new "qaoa" formulation, restarted from the single-start SPIQ JSONs of Week105–109 (`--spiq_starts 1`). Started with `bash logs/run_nft.sh <idx> <week> <spiq_week>`. The readouts are in `outputs/nft/WeekNN/` (under `.../reps_2/NFT/`), the response pickles in `outputs/nft/energy/WeekNN/`, and the logs in `logs/nft_WeekNN_inputN.log`.

| Week | Problem | Notes |
|---|---|---|
| Week112 | P1 (start from Week105) | 1.176 = ground; at best plan 1.0 |
| Week113 | P2 (start from Week106) | 4.860 (COBYLA 5.100, exact 3.653); at best plan 0 raw / 0.0001 fallback |
| Week114 | P3 (start from Week107) | 2.334 = ground; at best plan 1.0 |
| Week115 | P4 (start from Week108) | 7.390 (COBYLA 7.380, exact 4.908); at best plan 0 raw / 0.252 fallback |
| Week116 | P5 (start from Week109) | 17.504 (COBYLA 17.482, exact 8.340); at best plan 0 |

Same setup with **10000 evaluations**, started with `bash logs/run_nft.sh <idx> <week> <spiq_week> <1=COBYLA|3=NFT> 10000`. The readouts are in `outputs/long/WeekNN/`, the energy logs and pickles in `outputs/long/energy/WeekNN/`, and the container logs in `logs/long_WeekNN_inputN.log`.

| Week | Problem | Notes |
|---|---|---|
| Week117 | P4, COBYLA (start from Week108) | Stopped by itself after 3843 evaluations; 7.387; at best plan 0 raw / 0.250 fallback |
| Week118 | P5, COBYLA (start from Week109) | Stopped by itself after 6820 evaluations; 17.461; at best plan 0 |
| Week119 | P4, NFT (start from Week108) | 10000 evaluations, **6.195**; at best plan 0 raw / **0.491** fallback |
| Week120 | P5, NFT (start from Week109) | 10000 evaluations, **15.661** (still improving); best plan 1605 in 3 of 10240 samples (fallback only) |

Week102–104 use the same settings with the new formulation, so their energies are on the "qaoa" scale (exact 1.176 / 3.653 / 2.334). Their SPIQ files end in `_qaoa`, and each week's `energy/` folder holds the response pickle (`response_pickle_trial1_qaoa`). Unlike Week93–95, the readouts have no `#` run-note line; the settings are here and in the logs. Plots: `graphs/formulation.rmd` sections 4–6.

## Archived runs (`outputs/`)

`outputs/<method>/energy/WeekNN` holds the energy logs, and `outputs/<method>/WeekNN` holds the readouts.

| Folder | Method | Qubits | Params | Min energy | Matches |
|---|---|---|---|---|---|
| spiq/Week60 | SPIQ | 20 | 268 | 9.786 | P3, same QUBO as now (bitstring energies match exactly). Started from a Clifford point at 9.87 that isn't in any saved SPIQ JSON; the June and current SPIQ bests are 14.75 and 13.87 |
| spiq/Week62 | SPIQ | 4 | 28 | 2.000 | old 4-qubit problem |
| spiq/Week81 | SPIQ | 4 | 28 | 1.383 | old 4-qubit problem |
| spiq/Week84 | SPIQ | 12 | 116 | 8.273 | P2 |
| spiq/Week85 | SPIQ | 4 | 28 | 1.383 | old 4-qubit problem |
| spiq/Week88 | SPIQ | 12 | 116 | 8.263 | P2 |
| uninitialized/Week4 | SPIQ-shaped (116 params) despite the folder | 12 | 116 | 8.251 | P2 |
| uninitialized/Week23 | Random, reps 2 and 4 | 20 | 4 | -0.339 | P3 size. Energies are probably on the Ising scale (logged before the offset fix): add 25.80 to get the QUBO scale |
| uninitialized/Week24 | Random | 20 | 4 | -3.224 | P3. Energies are on the **Ising scale** (verified by re-simulating its logged parameters): add 25.80 to get the QUBO scale |
| uninitialized/Week71 | Random | 4 | 4 | 2.754 | old 4-qubit problem |
| uninitialized/Week71/Week51 | Random | 4 | 4 | -1.383 | old 4-qubit problem |
| uninitialized/Week72/Week62 | Random, pair of spiq/Week62 | 4 | 4 | 2.989 | old 4-qubit problem |
| uninitialized/Week74/Week84 | Random, pair of spiq/Week84 | 12 | 4 | 19.696 | P2 |
| uninitialized/Week96 | Random, **"qaoa" formulation**, 1000 iterations (stopped after 123 evals) | 3 | 4 | 1.929 | P1 (exact 1.176) |
| uninitialized/Week97 | Random, **"qaoa" formulation**, 1000 iterations (stopped after 126 evals) | 8 | 4 | 8.938 | P2 (exact 3.653) |
| uninitialized/Week98 | Random, **"qaoa" formulation**, 1000 iterations (stopped after 137 evals) | 8 | 4 | 5.507 | P3 (exact 2.334) |

| uninitialized/Week99 | Random, **"q2o" formulation**, 1000 iterations (127 evals), same code as Week96–98 | 5 | 4 | 2.710 | P1 (exact 1.031) |
| uninitialized/Week100 | Random, **"q2o" formulation**, 1000 iterations (120 evals) | 12 | 4 | 19.269 | P2 (exact 4.766) |
| uninitialized/Week101 | Random, **"q2o" formulation**, 1000 iterations (112 evals); costs use the fixed checker (best = 29) | 20 | 4 | 22.758 | P3 (exact 2.725) |

Plots for Week96–107 (and Week93–95 for comparison): `graphs/formulation.rmd`.

Week99–101 are the like-for-like old-formulation partners of Week96–98: same start angles (0.5 each), settings and code; only `qubo-formulation` differs. Each week's `energy/` folder also holds the response pickle (`response_pickle_trial1_<formulation>`).

Week96–98 use the new formulation (`docs/problem-formulation.md`), so their energies are on a different scale from every other row. Compare them by optimal ratio, not by energy.

## Plots in `graphs/multi-spiq.rmd` (`plot_energy_comparison`)

| Plot | Random | Single-start SPIQ | Multi-start SPIQ | Reference |
|---|---|---|---|---|
| P1 | uninitialized/Week71 (4 qubits, **not P1**) | multi-spiq/Week90 | — | 1.031 |
| P2 | uninitialized/Week74/Week84 | spiq/Week88 | multi-spiq/Week91 | 4.766 |
| P3 | uninitialized/Week24 (Ising scale; plotted with `random_offset` = 25.80) | spiq/Week60 (better start point) | multi-spiq/Week92 | 2.725 |

`graphs/seeded-multi-spiq.rmd` uses the same random and single-start baselines. Its multi-start curve is the seeded, diverse run: P1 = multi-spiq/Week93 (single-start baseline multi-spiq/Week90), P2 = multi-spiq/Week94, P3 = multi-spiq/Week95. Those runs used 1000 iterations, so their files are under `iterations_1000`.

P1's random baseline is a different problem. P3's random baseline is plotted with +25.80 (the Ising offset) to put it on the same scale. P3's SPIQ runs share the same QUBO and circuit but start from different Clifford points (Week60: 9.87, Week92: 13.87), so they differ because of the starting point, not the method.
