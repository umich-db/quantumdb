# Join Order Optimization on Gate-Based Quantum Computers via SPIQ-Initialized QAOA

Code for *"Improving Join Order Optimization on Gate-Based Quantum Computers via
Structured Parameter Initialization"* (Shekar, Wu, Bharadwaj, Ravi, Ma —
VLDB 2026 Workshop QCDKM). The work adapts the native join-ordering QUBO
encoding of Schönberger et al. to QAOA and initializes QAOA with **SPIQ**
(Scalable Parameter Initialization for QAOA), a Clifford-based classical search.
All experiments run on a noiseless simulator.

The repository started as the SIGMOD'23 reproduction package *"Ready to Leap
(by Co-Design)? Join Order Optimisation on Quantum Hardware"*; the upstream
D-Wave / co-design code has been removed.

---

## 1. Pipeline (paper Fig. 1)

```
 Query graph            base/ExperimentalAnalysis/IBMQ/QPUPerformance/Problems/JSON/<idx>_predicates/
 (card, pred, pred_sel)   card.txt  pred.txt  pred_sel.txt
        │  Scripts/ProblemGenerator.py
        ▼
 QUBO (§3.1)            Scripts/QUBOGenerator.py  generate_IBMQ_QUBO_for_left_deep_trees_v2
        │  qubo.to_ising()            (R+P)(R-2) binary variables, no slack variables
        ▼
 SPIQ init (§3.2)       spiq_initialization.py + clapton/   ── SPIQ environment ──
        │  writes spiq_initial_point_*.json + spiq_pcirc_*.qpy
        ▼
 QAOA (§3.2, §4)        IBMQExperiments.py [--spiq_json …]  ── QAOA environment ──
        │  writes energy_per_iteration_*.csv, min_state_readout.csv, results.txt (pickle)
        ▼
 Post-processing (§3.3) postprocess_results.py + Scripts/Postprocessing.py
        │  writes readout_summary.csv, readout_summary_eval1.csv
        ▼
 Figures / Table 1      visualization.rmd
```

| File | Role |
|------|------|
| `base/Scripts/ProblemGenerator.py` | Loads a query graph from `card.txt` / `pred.txt` / `pred_sel.txt`. |
| `base/Scripts/QUBOGenerator.py` | Native QUBO: validity penalties (H_A, H_B, H_pred) + squared log intermediate cardinality cost. |
| `base/spiq_initialization.py` | Relaxes the QAOA ansatz, runs the clapton genetic algorithm over Clifford angles, and writes the initial points. |
| `clapton/` | Vendored CAFQA/SPIQ Clifford-search library (stim + pygad). |
| `base/IBMQExperiments.py` | QAOA driver: random-init baseline or SPIQ-initialized relaxed ansatz, COBYLA. |
| `base/postprocess_results.py` | Re-samples chosen iterations, decodes final samples, prints the exact ground-state energy. |
| `base/Scripts/Postprocessing.py` | Bitstring → score vector → join order, plus fallback. Costs each plan. |
| `base/config.py` | `ibmq-processing` (`cpu` = local simulator) and IBM Q credentials (`IBMQ_TOKEN` env var). |
| `visualization.rmd` | R notebook that plots energy convergence and cost distributions. |

---

## 2. Environments

The two stages need incompatible qiskit stacks (paper §4), so use two virtual environments:

| Stage | Python | Requirements |
|-------|--------|--------------|
| QUBO + QAOA + post-processing | 3.8 | `requirements.txt` (qiskit 0.34.2, qiskit-optimization 0.3.2, docplex) |
| SPIQ initialization | separate venv | `requirements-spiq.txt` (qiskit-aer 0.13.3, qiskit-algorithms 0.3.1, stim, pygad, …) |

The `Dockerfile` builds the QAOA environment (`docker run … ibmq` runs `scripts/run_ibmq.sh`).

---

## 3. Evaluation problems (paper §5.1)

Only problem folder `0_predicates` is run by `IBMQExperiments.py`. To run a
problem, copy its values into `0_predicates/{card,pred,pred_sel}.txt`.
The SPIQ output names record the shape (`…_3rel_2pred`, `…_4rel_2pred`,
`…_4rel_6pred`).

| Paper | Relations (card) | Predicates (selectivity) | Qubits = (R+P)(R-2) |
|-------|------------------|--------------------------|--------|
| P1 | 10, 15, 20 | (0,1) 0.1, (1,2) 0.1 | 5 |
| P2 | 10, 15, 20, 30 | (0,1) 0.1, (2,3) 0.1 | 12 |
| P3 | 10, 15, 20, 30 | 6 predicates, 0.1 … 0.6 (see `03_predicates`) | 20 |

---

## 4. Running an experiment

```bash
cd base

# 1. SPIQ pre-pass (SPIQ environment)
python3 spiq_initialization.py --input_idx 0 --reps 2 --n_gens 4000 --out_dir ../spiq_init_outputs

# 2a. SPIQ-initialized QAOA (QAOA environment), one run per trial
python3 IBMQExperiments.py --trial 1 --reps 2 --optimizer 1 --week Week84 \
    --spiq_json ../spiq_init_outputs/spiq_initial_point_input0_reps2_4rel_2pred.json

# 2b. Random-initialization baseline: same command without --spiq_json
#     (use a different --week so results do not overwrite each other)
python3 IBMQExperiments.py --trial 1 --reps 2 --optimizer 1 --week Week85

# 3. Post-process (run from the repository root)
cd ..
python3 base/postprocess_results.py --trial 1 --reps 2 --week Week84
```

### `spiq_initialization.py` flags
* `--input_idx`: problem folder `<idx>_predicates`.
* `--reps`: QAOA depth p (2 in the paper).
* `--n_gens`: GA generation budget. `claptonize` receives `n_gens // 2`.
* `--n_proc`, `--n_starts`, `--n_rounds`: parallelism and restarts. `--err`: optional depolarizing noise during the search.

### `IBMQExperiments.py` flags
* `--trial`: trial id, used in result paths.
* `--reps`: QAOA depth p.
* `--optimizer`: 0 = AQGD, 1 = COBYLA (paper), 2 = SPSA.
* `--spiq_json`: turns on SPIQ mode.
* `--week`: top-level results directory.
* `--iterations`: max optimizer iterations (default 10000).

### `postprocess_results.py` flags
`--trial` (one or more), `--reps`, `--optimizer`, `--input_idx`,
`--iterations`, `--week`, `--evals` (evaluations to re-simulate, default `1`).

---

## 5. How SPIQ is wired in (`spiq_initialization.py` + `clapton/`)

Every parametric `Rz` in the QAOA ansatz is restricted to a Clifford rotation
`Rz(k·π/2)`, `k ∈ {0,1,2,3}`. That makes the circuit simulable in polynomial
time with **stim**. clapton's genetic algorithm then searches the integer
vector `K` that minimises `⟨H_C⟩`.

**Relaxation + angle recovery.** Three details make the stim result
reproducible in qiskit:

1. **Relaxation puts the coefficient into the parameter *name*.**
   `clapton.relax_qaoa_parameters` replaces each expression such as
   `-0.977 * γ[0]` with a fresh per-gate parameter named `"-0.977*gamma_0"`,
   applied as `Rz(1.0 · θ)`. The *applied* multiplier is therefore 1.0; the
   *original* multiplier survives only in the name.
2. **`str(expr).split("*")[0]` is fragile**, so `_extract_true_multipliers`
   evaluates each `ParameterExpression` at `param = 1.0` numerically.
3. **Signs matter.** The vanilla ansatz applies `Rz(mult·γ)` literally, so the
   vanilla angle is `θ = k·π/2 / mult` with the *signed* multiplier. Using
   `abs(mult)` swaps `S ↔ S†` on every negative-coefficient gate.

The script therefore produces two initial points:
* **`relaxed_initial_point`**: one `θ_i = k_i·π/2` per gate of `pcirc`.
  `IBMQExperiments.py --spiq_json` uses this one.
* **`initial_point`**: `2·reps` angles for a stock `QAOAAnsatz`, averaged per layer.

**Built-in checks.** `spiq_initialization.py` binds `relaxed_initial_point`
into `pcirc` and compares the qiskit `Statevector` energy with stim's
`energy_best`; it warns if the relative error is above `1e-4`.
`IBMQExperiments.py` repeats the check with shots (QUBO energy − Ising
offset vs `energy_best`, tolerance 0.25) before optimising.

**Outputs** (`spiq_init_outputs/`, stub = `input{idx}_reps{r}_{R}rel_{P}pred`):

| File | Content |
|------|---------|
| `spiq_initial_point_<stub>.json` | Initial points, parameter names, `energy_best` (Ising), `energy_best_qubo`, `ising_offset`, `ks_best_raw`, problem definition, exact ground-state energy, path to the QPY file |
| `spiq_pcirc_<stub>.qpy` | The relaxed circuit, so QAOA binds angles to exactly the circuit SPIQ scored |
| `spiq_trace_<stub>.txt` | GA generation trace |

---

## 6. QAOA driver (`IBMQExperiments.py`)

* **`solve_with_QAOA`** (random-initialization baseline): stock qiskit `QAOA`
  over `2·reps` angles, all starting at 0.5. A callback logs every evaluation.
* **`solve_with_QAOA_spiq`** (SPIQ): loads `pcirc` from QPY. COBYLA then
  optimises all per-gate angles, starting from `relaxed_initial_point` and
  minimising `Σ_x p(x)·qubo.objective(x)` over 10 240 shots.

Both solvers log energies on the **QUBO scale** (Ising expectation + offset).
Both return `(response, final_point, used_eval, min_state_buffer)`. At the
end, both re-sample the lowest-energy parameters they saw.

Result layout (relative to `base/`):

```
{week}/ExperimentalAnalysis/IBMQ/QPUPerformance/Results/CPU_Data/
    iterations_{N}/reps_{p}/{OPTIM}/input{i}/trial{T}/
        energy_per_iteration_{N}_{OPTIM}_{p}_{T}.csv   # iteration, energy, paramter, std
        min_state_readout.csv                          # bitstring, energy, prob
ExperimentalAnalysis/IBMQ/QPUPerformance/Results/CPU_Data/
    {N}_Iterations/{i}_predicates-newQUBO/trial{T}/results.txt   # pickled response
```

---

## 7. Post-processing and metrics (§3.3, §5.2)

`Scripts/Postprocessing.readout` decodes every sampled bitstring twice:
* **fallback = False**: the relation-join block becomes an `R × (R-2)` matrix.
  Each relation's score is its weighted row sum, with earlier joins weighted
  higher. Sorting the scores gives the join order.
* **fallback = True**: Schönberger et al.'s fallback walks the query graph in
  score order. It prefers relations connected by a predicate, so cross
  products are used only when no connected relation is left.

Each plan is costed as the sum of intermediate cardinalities. Each row of
`readout_summary*.csv` holds bitstring, join order, cost, `used_fallback`,
energy, count and probability. From these CSVs and the energy logs,
`visualization.rmd` derives the paper's metrics:

| Metric | Source |
|--------|--------|
| Cost ratio (Table 1) | `readout_summary.csv` of the final state, split by `used_fallback` |
| Optimal ratio, first vs final iteration | `readout_summary_eval1.csv` vs `readout_summary.csv` |
| Energy convergence (Figs. 3–5) | `energy_per_iteration_*.csv` + ground-state energy printed by `postprocess_results.py` |

Paper results live in `outputs/spiq/` and `outputs/uninitialized/`.

---

## References

[1] Manuel Schönberger, I. Trummer, W. Mauerer. *Quantum-Inspired Digital Annealing for Join Ordering.* PVLDB 17(3), 2024.
[2] Manuel Schönberger, S. Scherzinger, W. Mauerer. *Ready to Leap (by Co-Design)? Join Order Optimisation on Quantum Hardware.* SIGMOD 2023.
[3] D. Bharadwaj, Y. Hou, G.-Y. Li, G. S. Ravi. *Scalable Clifford-Based Classical Initialization for the Quantum Approximate Optimization Algorithm.* arXiv:2602.14327, 2026.
