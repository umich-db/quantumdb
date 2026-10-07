# Join-order problem formulation for QAOA

A living record of the QUBO/Hamiltonian formulation: what it is, what is wrong with it, what we changed, and what experiments showed.
Update it with every formulation change and every experiment that tests one. `CHANGELOG.md` still records code changes; this file records the reasoning and results.

Problems used throughout (`base/ExperimentalAnalysis/IBMQ/QPUPerformance/Problems/JSON/`):

| | Relations (card) | Predicates (selectivity) | True optimum C_out |
|---|---|---|---|
| P1 | 10, 15, 20 | (0,1) 0.1, (1,2) 0.1 | 15 |
| P2 | 10, 15, 20, 30 | (0,1) 0.1, (2,3) 0.1 | 315 |
| P3 | 10, 15, 20, 30 | (0,1) 0.1, (1,2) 0.2, (2,3) 0.3, (0,2) 0.4, (0,3) 0.5, (1,2) 0.6 | 29.4 (both (1,2) predicates applied) |

---

## Status

| Item | State |
|---|---|
| Analysis of the current (Q2O / VLDB'24) formulation | done (2026-10-07) |
| New QAOA-oriented QUBO (`generate_qaoa_qubo_left_deep`) | planned |
| Evaluator fix: apply every predicate on a repeated relation pair | planned |
| Brute-force self-check `base/test_qubo_formulation.py` | planned |
| SPIQ + QAOA runs with the new formulation | planned |

---

## 1. The current formulation

Source: `base/Scripts/QUBOGenerator.py::generate_IBMQ_QUBO_for_left_deep_trees_v2`. It follows the native encoding of Schönberger, Trummer and Mauerer (VLDB'24), which was designed for digital annealing.

- **Variables:** `v[t,j]` means relation t is in join j, for J = R−2 encoded joins; the last join contains every relation and is not encoded. `w[p,j]` means predicate p is applied at join j. That is (R+P)(R−2) qubits.
- **Constraints:**
  - `H_A = Σ_j (j+2 − Σ_t v_tj)²` fixes join j at j+2 relations.
  - `H_B = Σ v_t,j−1 (1 − v_tj)` makes a relation, once joined, stay joined.
  - `H_pred = Σ w_pj (2 − v_aj − v_bj)` makes `w ≤ v_a, v_b`.
- **Cost:** `H_cost = Σ_j L_j²` with `L_j = Σ_t log c_t v_tj + Σ_p log s_p w_pj`, the log of intermediate result j.
- **Total:** `H = λ (H_A + H_B + H_pred) + H_cost`, with λ = J.
- **Hamiltonian:** `from_docplex_mp(model).to_ising()` substitutes x_i = (1 − Z_i)/2, which gives `Σ h_i Z_i + Σ J_ij Z_i Z_j + offset`. This translation is exact, and the offset is handled consistently in `IBMQExperiments.py` and `spiq_initialization.py`.
- **Circuit:** `QAOAAnsatz(op)` is standard QAOA: initial state |+⟩ⁿ, cost layer RZ/RZZ, mixer RX. The squared cost puts a ZZ term on every v/w pair inside a join column, so the circuit is dense.

The Hamiltonian and circuit match the QUBO correctly. The defects are in the QUBO itself.

## 2. Findings (2026-10-07)

### 2.1 Root cause of the suboptimal samples: infeasible ground state
Brute-forcing every bitstring of the current QUBO shows the following:
- **Valid plans are ranked correctly.** The lowest-energy valid plan is the true optimum for P1, P2 and P3.
- **The penalty weight is too small.** λ = J is not derived from the cost scale. One unit of violation costs λ but can save more than λ in `H_cost`.

| | λ used | Exact threshold λ* | Safe bound (min valid H_cost) | Invalid states below the best valid one | Ground state |
|---|---|---|---|---|---|
| P1 | 1 | 1.352 | 1.383 | 2 | E=1.031: {0,1} plus an illegal predicate var (1,2) that drives L to 0.18. The 2nd state is {1,2} plus an illegal predicate, which decodes to **cost 30**. This explains the observed ~50/50 split between 15 and 30. |
| P2 | 2 | 4.753 | 7.519 | 10 | E=4.766: v = {0,1},{0,1}, so join 2 is missing a relation. It decodes to [1,0,3,2], **cost 465**. This is the observed 99.99% at 465. |
| P3 | 2 | 1.156 | 2.725 | 0 | valid and optimal (29.4) |

- **λ\*** is the exact smallest weight for which the ground state is valid: λ\* = max over invalid x of (best valid H_cost − H_cost(x)) / penalty(x). It comes from brute force over every bitstring, so it is only computable for small problems.
- **The safe bound** is guaranteed but loose. Worked examples are in §4.

The squared cost makes this worse. `L_j²` rewards anything that pushes L_j toward **0**, including dropping a relation or turning on an inapplicable predicate. Each saves roughly 2·L·Δ, which is far more than λ.

### 2.2 Are the constraints necessary and sufficient?
- **H_A + H_B = 0 ⇔ valid left-deep plan.** The columns are nested sets of size 2, …, R−1. This is necessary and sufficient, up to swapping the first two relations. Nothing in it is redundant.
- **H_pred is one-sided.** It allows a predicate to be off even when both of its relations are present, and relies on the cost to switch it on. Under the square, if L_j would go negative, leaving the predicate off is cheaper, so selectivity is under-reported. This does not happen in P1–P3.
- **The penalty weight is insufficient.** All penalty terms are integers, so any violation costs at least λ. A sufficient condition for a feasible ground state is therefore λ > min_valid H_cost − min_all H_cost. With the squared cost min_all is 0. λ = J does not meet this condition.
- **Dead code:** `get_log_values(num_decimal_pos)` rounding is left over from the threshold formulation.
- **Qubit reduction:** the P·J predicate qubits can be removed by substituting w_pj = v_aj·v_bj (see §3).

### 2.3 Repeated predicate pairs (P3)
P3 lists (1,2) twice, with selectivities 0.2 and 0.6. This means two predicates between the same two tables, e.g. `A.x = B.x AND A.y = B.y`. Assuming they are independent, the combined selectivity is the product 0.2·0.6, and both the cost and the energy should reflect it.
- The QUBO already applies both.
- `Postprocessing.get_selectivity_for_new_relation` uses `pred.index`, which applies only the first.

As a result the evaluator reports the P3 optimum as 39 while the QUBO's is 29.4. It is the same plan, so the optimal ratio is unaffected, but the energy and cost columns disagree.

### 2.4 Cost functions compared
- **Current (VLDB'24):** `Σ_j L_j²`. This is a convex surrogate in log space.
- **Ready to Leap (SIGMOD'23).** This is from memory of the paper; re-check against the text before citing it.
  - It uses the Trummer & Koch MILP: threshold indicators `cto_{r,j}` are set when log|T_j| exceeds log θ_r, and the cost is `Σ_j Σ_r Δθ_r · cto_{r,j}`.
  - That is a step-function approximation of the *actual* cardinality, and it is linear in qubits.
  - Inequalities become equalities with binary slack qubits, and log values are discretised.
  - The cost is monotone in cardinality but quantised, so plans in the same bucket get the same energy. Its accuracy depends on where the thresholds are placed.
  - Big-M and slack penalties make the coefficients large.
- **Would Ready to Leap be better? No.** Being gate-based does not make it QAOA-friendly. It is still a penalty QUBO. Its slack and threshold qubits exceed the 23-qubit limit and make the λ problem worse. Its one advantage, a cardinality-scale cost, is not what is failing here.

Surrogate fidelity against true C_out over all valid plans, as Kendall τ and whether the surrogate's best plan is the true optimum:

| | Σ L² (current) | Σ L (linear) | max L |
|---|---|---|---|
| P1 | 1.00 / correct | 1.00 / correct | 1.00 / correct |
| P2 | 0.76 / correct | 0.73 / correct | 0.78 / correct |
| P3 | 0.94 / correct | 0.94 / correct | 0.93 / correct |

The square adds nothing to the ranking. It is also the term that forces the predicate qubits and creates the incentive to push L toward 0.

## 3. Proposed formulation (QAOA-oriented, still a QUBO)

Add a new builder `generate_qaoa_qubo_left_deep(card, pred, pred_sel)` in `base/Scripts/QUBOGenerator.py`:
1. **Remove the predicate variables and use a linear log cost.** The cost becomes `H_cost = Σ_j (Σ_t log c_t v_tj + Σ_p log s_p v_aj v_bj)`, which is still quadratic.
   - Qubits drop from (R+P)(R−2) to R(R−2): P1 5→3, P2 12→8, P3 20→8.
   - `H_pred` disappears, and the incentive to push L toward 0 goes with it.
2. **Derive λ from the cost scale:** λ = H_cost(identity-order plan) − Σ_j Σ_p min(0, log s_p) + 1.
   - This guarantees a feasible ground state.
   - Keep `penalty_scaling` as the tuning knob.
   - Keep λ as small as is safe. A large λ squeezes the valid-plan energy range (about 2) inside the full range (about 150), which hurts QAOA's angle resolution.
   - This rule is up to 30× looser than needed. Prefer λ = max_t log c_t + margin, keeping the safe rule as the fallback (see §4.5).
3. Keep `H_A` and `H_B` unchanged.

Brute-force pre-check, done in pure Python: the ground state is valid and optimal for P1–P3 with λ = 4.2, 8.7, 9.6.

| | λ | Gap to 2nd valid plan | Valid E range | Full E range |
|---|---|---|---|---|
| P1 | 4.18 | 0.301 | 1.12 | 15.5 |
| P2 | 8.65 | 0.176 | 1.95 | 146.4 |
| P3 | 9.62 | 0.380 | 2.83 | 163.0 |

Wiring:
- `base/config.py`: add `"qubo-formulation": "q2o" | "qaoa"`.
- Add `QUBOGenerator.FORMULATIONS = {"q2o": ..., "qaoa": ...}`. The callers in `IBMQExperiments.py`, `spiq_initialization.py` and `postprocess_results.py` look the builder up through it.
- `spiq_initialization.py`: add the formulation to `shape_suffix`, so `.qpy` files with different qubit counts don't collide.
- The decoder needs no change, because `readout` already slices the first R(R−2) bits.
- **Evaluator fix:** `get_selectivity_for_new_relation` multiplies every matching predicate. P3's target in `graphs/seeded-multi-spiq.rmd` changes from 39 to 29.4.

Deferred, with the condition for revisiting each:
- **Squared-cost HUBO** (degree 4, predicate vars substituted). QAOA can run it natively. Revisit if the linear surrogate ranks plans worse than the squared one on larger problems.
- **Exact per-join C_out polynomial** (≤ 2^R terms per join). Revisit if a surrogate mis-ranks optima on larger problems.
- **One-hot position encoding with an XY mixer.** It needs no λ, but costs R(R−1) qubits and a custom mixer in SPIQ/Clapton.
- **Binary entry-time encoding.** It only saves qubits for R ≥ 5.

Verification:
- `base/test_qubo_formulation.py` (assert style) checks, for P1–P3 by brute force:
  - the ground state is valid;
  - the decoded cost equals the true optimum;
  - the qubit count is R(R−2).
- SPIQ + QAOA on P1–P3 with `"qubo-formulation": "qaoa"`, comparing optimal ratios against Week93–95.

## 4. Worked numerical examples

All values are base-10 logs. For P1 and P2: log 10 = 1, log 15 = 1.17609, log 20 = 1.30103, log 30 = 1.47712, log 0.1 = −1.
These are exact evaluations of the energy function, not circuit simulations. QAOA runs are deferred to the container.

### 4.1 P2: why the 465 plan wins under the current penalty
Two encoded joins: join 1 has 2 relations and join 2 has 3. Predicates: (0,1) and (2,3), each with selectivity 0.1.

**State O (valid, optimal plan [0,1,2,3], C_out = 15 + 300 = 315)**
- Join 1 is {0,1} with the predicate on: L₁ = 1 + 1.17609 − 1 = 1.17609, so L₁² = 1.38319.
- Join 2 is {0,1,2} with the predicate on: L₂ = 1 + 1.17609 + 1.30103 − 1 = 2.47712, so L₂² = 6.13612.
- Penalty is 0, so **E_O = 7.51931 for any λ**.

**State X (invalid: relation 2 dropped from join 2)**
- Join 1 is {0,1}: 1.38319.
- Join 2 is {0,1} instead of 3 relations: L₂ = 1.17609, so L₂² = 1.38319.
- H_A = (3 − 2)² = 1. H_B = 0 and H_pred = 0.
- **E_X = λ·1 + 2.76638.** With λ = 2 this is **4.766 < 7.519**, so X is the ground state.

**Decoding X.** The v rows are r0 = [1,1], r1 = [1,1], r2 = [0,0], r3 = [0,0]. With weights [2,1] the scores are [3,3,0,0]. `argsort` reversed gives [1,0,3,2]. Relations 2 and 3 tie, and the index order of the tie puts 3 first. The plan cost is 15 + 15·30 = **465**, the second-best plan. This is the 99.99% observed in Week94.

**Threshold.** E_X > E_O requires λ > 7.51931 − 2.76638 = **4.75293** = λ\*. At λ = 4, X still wins: 6.766 < 7.519.

**The same state in the proposed linear formulation (no predicate qubits)**
- E_O = L₁ + L₂ = 1.17609 + 2.47712 = 3.65321.
- E_X = λ + 1.17609 + 1.17609 = λ + 2.35218.
- The threshold is λ > **1.30103**, which is exactly log 20, the log-cardinality of the dropped relation.

### 4.2 Why the squared cost inflates the penalty needed
Dropping a relation with log-cardinality ℓ from a join with log-size L saves:

| Cost | Saving | Example (P2: L = 2.477, ℓ = 1.301) |
|---|---|---|
| Squared (q2o) | L² − (L − ℓ)² = 2Lℓ − ℓ² | 4.753 |
| Linear (proposed) | ℓ (minus any predicates it enabled, which are negative) | 1.301 |

- **Scaling.** The squared saving grows with L, the size of the whole intermediate result. The linear saving is bounded by one relation's log-cardinality.
- **Estimate for a 10-relation query** with cardinalities around 10⁵ (ℓ ≈ 5, late-join L ≈ 20):
  - The squared form needs λ of about 2·20·5 − 25 = **175** per violation.
  - The linear form needs λ of about **5**.
  - The optimal-vs-second-best gap is O(1) in both, so in the squared form that gap sits inside a range about 35× wider.

### 4.3 P1: the illegal-predicate state behind cost 30
One encoded join of size 2. Predicates: (0,1) and (1,2), each with selectivity 0.1.

| State | v | w | L | L² | Penalty | E at λ = 1 | Decodes to |
|---|---|---|---|---|---|---|---|
| O (valid) | {0,1} | (0,1) | 1.17609 | 1.38319 | 0 | 1.383 | 15 |
| X | {0,1} | (0,1), (1,2)✗ | 0.17609 | 0.03101 | H_pred = 1 | **1.031** | 15 |
| Y | {1,2} | (1,2), (0,1)✗ | 0.47712 | 0.22764 | H_pred = 1 | **1.228** | **30** |
| Valid {1,2} | {1,2} | (1,2) | 1.47712 | 2.18188 | 0 | 2.182 | 30 |

✗ marks a predicate switched on although one of its relations is absent.

- Both X and Y sit below O. Each pays λ = 1 for one illegal predicate so that it can subtract another −1 inside the square.
- The ground state X happens to decode to the right plan. Y, the next state, decodes to 30, which explains the observed split.
- Threshold: λ > 1.38319 − 0.03101 = **1.352**.
- In the proposed formulation this state cannot exist. The predicate term is log s·v₁v₂, which is zero unless both relations are present.

### 4.4 Full Hamiltonian of P1 in the proposed formulation
There are 3 qubits, v₀, v₁ and v₂.

**QUBO:**
`H = λ(2 − v₀ − v₁ − v₂)² + 1·v₀ + 1.17609·v₁ + 1.30103·v₂ − v₀v₁ − v₁v₂`

- Valid states give E = log C_out exactly: {0,1} → 1.17609 = log 15, {1,2} → 1.47712 = log 30, {0,2} → 2.30103 = log 200.
- With a single join the linear cost is exactly the log of the true cost, so the energy order equals the cost order.

**Ising form**, with v = (1 − Z)/2:
- Cost part: 1.23856 − 0.25 Z₀ − 0.08805 Z₁ − 0.40051 Z₂ − 0.25 Z₀Z₁ − 0.25 Z₁Z₂
- Penalty part: λ·(1 + ½(Z₀ + Z₁ + Z₂) + ½(Z₀Z₁ + Z₀Z₂ + Z₁Z₂))

  This follows because 2 − s = (1 + ΣZ)/2, so (2 − s)² = 1 + ½ΣZ + ½ΣZᵢZⱼ.
- The circuit has 3 RZ and 3 RZZ gates per layer. The current formulation needs 5 qubits, 5 RZ and 10 RZZ gates.

### 4.5 Penalty size vs. resolvable gap (static estimate)
QAOA has to resolve the energy gap between the optimal plan and the second-best plan. That gap is fixed by the cost, while the full spectrum range grows with λ. A smaller ratio means γ needs finer resolution, and noise or shot error can wipe out the difference. Ratio of gap to range:

| | λ = 1.1·λ\* | λ = safe rule | λ = 16 | λ = 50 |
|---|---|---|---|---|
| P1 q2o | 0.0550 | 0.0369 | 0.0061 | 0.0020 |
| P1 new | 0.2676 | 0.0194 | 0.0048 | 0.0015 |
| P2 q2o | 0.0069 | 0.0045 | 0.0025 | 0.0008 |
| P2 new | 0.0075 | 0.0012 | 0.0006 | 0.0002 |
| P3 q2o | 0.0082 | 0.0036 | 0.0009 | 0.0003 |
| P3 new | 0.0764 | 0.0023 | 0.0014 | 0.0004 |

The gap/range ratio roughly scales as 1/λ. The safe rule from §3 is loose: for P3 new it gives λ = 9.62 where λ\* = 0.294, about 30× too large. That costs up to 33× in resolvable gap.

**Suggestion.** For the linear formulation, use **λ = max_t log c_t + margin** in place of the safe rule.
- Rationale: a single dropped relation saves at most max_t log c_t (§4.2).
- It holds in P1–P3: max log c is 1.301, 1.477 and 1.477, against λ\* of 0.294, 1.301 and 0.294.
- It is not proven for swap-type H_B violations, where the nested sets are broken but the sizes are kept. So `test_qubo_formulation.py` should assert a valid ground state under this λ, and the code should fall back to the safe rule if a larger problem fails that check.

### 4.6 QAOA-relevant static properties per formulation

| | Qubits | Weight-1 / weight-2 Z terms (RZ / RZZ per layer) | Est. CNOTs per layer before routing (2 per RZZ) | Valid bitstrings / 2ⁿ | Share of the |+⟩ⁿ start that is valid |
|---|---|---|---|---|---|
| P1 q2o | 5 | 5 / 10 | 20 | 5 / 32 | 15.6% |
| P1 new | 3 | 3 / 3 | 6 | 3 / 8 | 37.5% |
| P2 q2o | 12 | 12 / 34 | 68 | 32 / 4096 | 0.78% |
| P2 new | 8 | 8 / 16 | 32 | 12 / 256 | 4.7% |
| P3 q2o | 20 | 20 / 94 | 188 | 252 / 1,048,576 | 0.024% |
| P3 new | 8 | 8 / 16 | 32 | 12 / 256 | 4.7% |

- In q2o, the valid count includes predicate-variable on/off choices. P3 has 252 valid bitstrings but only 12 distinct plans; the other bitstrings are valid but carry a worse cost because they leave an applicable predicate off.
- Expected effect of the proposed formulation:
  - **P3:** about 6× fewer two-qubit gates per layer, and a starting state about 195× richer in valid plans.
  - **P2:** about 2× fewer two-qubit gates and about 6× richer.
- These are estimates to confirm with container runs (§5).

## 5. Experiment log

Newest first. Each entry gives the date, the formulation and its settings, the problem, where the results are, and what they showed.

| Date | Formulation | Problem | Result | Location |
|---|---|---|---|---|
| 2026-10-07 | q2o and proposed linear formulation, several λ | P1–P3 | Static landscape analysis: exact λ\*, gap/range vs λ, share of valid states in the start, Z-term counts (§4). The safe λ rule is up to 30× too large, so max log c is suggested instead. | analysis only |
| 2026-10-07 | q2o, λ=J | P1–P3 | Exact brute force of the QUBO spectrum: the ground state is infeasible for P1 and P2 and decodes to costs 15/30 and 465 (§2.1). | analysis only |
| 2026-09-30 | q2o, λ=J | P1–P3 | Seeded multi-start SPIQ, share of samples at the optimum (final): P1 0.507, P2 0.0001 (99.99% at 465), P3 0.126 | `outputs/multi-spiq/Week93–95`, `graphs/seeded-multi-spiq.rmd` |
