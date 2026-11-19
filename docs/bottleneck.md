# Why QAOA doesn't reach the best plan on P4

**The question:** P4 (5 tables, 15 qubits, new "qaoa" formulation) has a best join order with cost 165. QAOA never returns that plan as a valid bitstring. Is the cause the formulation, the optimizer, the circuit, or something else?

**Short answer:**
- **Not the formulation's correctness.** The best plan is the single lowest-energy state of the Hamiltonian.
- **The main bottleneck is the optimizer getting stuck near the SPIQ start.** NFT ends at an energy worse than simply putting all the weight on a state it already has.
- **The shallow circuit (2 layers) is a second cause.**
- **Two properties of the formulation make the landscape harder:** a small energy gap between plans, and invalid states between neighbouring plans.

**Runs used:** all start from the Week108 single-start SPIQ point, with 2 layers and 10240 shots.
- Week117: COBYLA, 10000-evaluation budget; it stopped by itself at 3843.
- Week119: NFT, 10000 evaluations.

Both are described in `RESULTS_INDEX.md`, "P4 and P5 with 10000 evaluations". The energies below are exact QUBO values computed classically, with no simulation (λ = 1.1 · max log₁₀ card = 1.869).

---

## 1. Energies of the P4 states

| State | Bitstring | Valid? | Join order (cost) | Energy |
|---|---|---|---|---|
| **Best plan** | `111111011001000` | yes | [1, 0, 2, 3, 4] (**165**) | **4.908**, the lowest of all 2¹⁵ = 32768 states |
| Second-best plan | `111111001011000` | yes | [1, 0, 3, 2, 4] (330) | 5.483 |
| "Near-165" state | `101111011011000` | **no**: table 0 drops out at step 2 and comes back at step 3 | repair gives [1, 0, 2, 3, 4] (165); raw decoding gives 330 | 6.953 |
| Bad state A | `011011001111100` | **no**: table 4 drops out at step 2 | repair gives 3825; raw decoding gives 7200 | 8.829 |
| Bad state B | `001011011111100` | **no**: table 4 drops out at step 2 | repair gives 1665; raw decoding gives 2700 | 8.431 |

The 8 lowest energies over all 32768 states:

> 4.908 (best plan), 5.483 (330 plan), 5.511, 5.687, 5.687, 6.033, 6.175, 6.261

So five states lie within 0.8 of the lowest energy.

**How to read the two decodings:**
- **Raw** decodes the bitstring as it is, even when it's invalid.
- **Repair** (the "fallback" in the readouts) first fixes an invalid bitstring into a valid join order.

The "near-165" state decodes to 330 raw but to 165 after repair. That's why the share at the best plan is 0 with raw decoding but not with repair.

---

## 2. Share of each plan at the start and the final iteration

Share of the 10240 samples on each bitstring. "Start" is the readout at the first evaluation, which is the SPIQ point.

| State (energy) | COBYLA start | **COBYLA final** | NFT start | **NFT final** |
|---|---|---|---|---|
| Best plan, 165 (4.908) | 0% | **0%** | 0% | **0%** |
| Second-best plan, 330 (5.483) | 24.8% | **25.2%** | 25.2% | **50.7%** |
| Near-165, invalid (6.953) | 25.1% | **25.0%** | 25.1% | **49.0%** |
| Bad A, invalid (8.829) | 25.3% | **24.7%** | 24.7% | **~0%** |
| Bad B, invalid (8.431) | 24.8% | **25.1%** | 25.1% | **~0%** |
| Everything else | 0% | 0.1% | 0% | 0.3% |
| Distinct bitstrings | 4 | 9 | 4 | 19 |
| Average energy | 7.42 | **7.387** | 7.40 | **6.195** |
| Share at best plan, raw / repair | 0 / 0.25 | 0 / 0.25 | 0 / 0.25 | 0 / **0.49** |

**Check:** each state's share × its energy adds up to the average energy.
- Start: ¼ × (5.483 + 6.953 + 8.829 + 8.431) = 7.42.
- NFT final: 0.507 × 5.483 + 0.490 × 6.953 ≈ 6.19.

**What changed:**
- **COBYLA changed nothing.** The final state is the SPIQ state: four bitstrings at 25% each.
- **NFT dropped the two bad states and split the weight between the 330 plan and the near-165 state.** That closes 48% of the energy gap (7.40 → 6.195, with the lowest possible at 4.908).
- **Neither found a state that SPIQ didn't already contain.** The valid 165 bitstring never appears, in any run. The only route to 165 is the repair step fixing the invalid near-165 state.

---

## 3. Possible reasons, and what the numbers say

### 3.1 The formulation is correct, but makes the landscape hard

- **It encodes the right answer.** The best plan is the unique lowest-energy state, and no invalid state lies below it. Penalties A and B are strong enough.
- **The gaps between plans are small.** The cost term sums log₁₀ intermediate sizes, which squashes the differences between plans. The 165 and 330 plans are 0.575 apart in energy, while breaking one rule costs λ = 1.869. So the shape of the landscape is set mostly by the penalties, not by plan quality. Five states sit within 0.8 of the lowest energy, so the optimizer has to tell apart states that are very close.
- **Neighbouring valid plans are separated by invalid states.** Going from the 330 plan to the 165 plan means swapping tables 2 and 3 in step 2, which is 2 bit flips. Each single flip in between breaks a rule:
  - flip step 2 of table 2 on: `111111011011000`, energy 6.953 (step 2 then has 4 tables);
  - flip step 2 of table 3 off: `111111001001000`, energy 6.175 (step 2 then has 2 tables).

  So the path from the 330 plan to the best plan goes over a barrier 0.7–1.5 above the 330 plan.

### 3.2 The optimizer and the landscape: the main bottleneck

- **NFT ends in a local minimum, not at the best point it could reach.** Moving all the weight onto the 330 plan, a state it already has, would give 5.483, well below its final 6.195. So it didn't even find the best mix of the states it was already sampling.
- **Both optimizers are local.** They improve the angles step by step near where they start. The SPIQ start contains 4 states, none of them the best plan. Reaching it needs a large move over the barrier in 3.1, and neither COBYLA nor NFT makes jumps like that.
- **The landscape is rough.** There are 140 independent angles, and each energy is an estimate from samples. NFT needed about 3000 evaluations, roughly 21 passes over all the angles, before it found the first downhill direction. COBYLA stopped by itself at 3843 evaluations without moving.

### 3.3 The circuit: only 2 layers

- **With 2 layers, the circuit can only spread the starting state over nearby bitstrings by a limited amount.** It may not be able to put most of the weight on one bitstring, least of all one the start doesn't contain.
- **The final state also hints at a circuit limit.** NFT keeps the 330 plan and the near-165 state at about 50/50 rather than moving weight onto the lower one. Those two bitstrings differ in 2 bits. That suggests the angles near this point move both states together.

### 3.4 Minor factors

- **Shot noise.** With 10240 samples per energy, the estimate is off by about 0.01–0.02. That's small next to the 0.575 gap between plans, but it is enough to make COBYLA's steps shrink and stop.
- **The simulator isn't seeded.** Two runs from the same start split apart after a few evaluations: the 1000- and 10000-evaluation runs diverge at evaluation 3. One run per setting can be lucky or unlucky.

---

## 4. Tests that would separate the causes

| Test | Cost | If it works, the bottleneck was |
|---|---|---|
| Multi-start SPIQ on P4: does any start contain the 165 bitstring? This worked for P2. | about 1–2 h | the starting point |
| Start QAOA from a point whose samples include 165 | about 1 h | whether the optimizer can keep the right state once it has it |
| 3 layers, same SPIQ start | about 2–3 h | circuit depth |
| Exact energies from the full simulated state instead of 10240 samples | same as one run | shot noise |
| Plain QAOA with 4 shared angles instead of 140 | under 1 h | too many independent angles |
| A second NFT run at 10000 evaluations (different trial) | about 1.5 h | whether the drop after ~3000 evaluations is repeatable |

Suggested first step: **multi-start SPIQ on P4.** It's the cheapest test and it fixed P2.

---

## Reproduce

- **Energies:** `qubo.objective.evaluate(bits)` on the P4 QUBO from `Scripts.QUBOGenerator.FORMULATIONS["qaoa"]`. Bit i of the string is variable i, so `v[t, j]` sits at position 3t + j.
- **Shares:**
  - start: `outputs/long/Week117/` and `Week119/`, in `.../input3/trial1/readout_summary_eval1.csv`;
  - final: `.../trial_1/readout_summary.csv`.

  In each, count the bitstrings in the `# all_solutions` block, using rows with `used_fallback = False`.
