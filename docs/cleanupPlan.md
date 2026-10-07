# Clean up `spiq-joo` to the paper's pipeline + document it

## Context
The repo grew from the SIGMOD'23 "Ready to Leap" reproduction package into the SPIQ-JOO work described in
*QCDKM'26 "Improving JOO on Gate-Based Quantum Computers via Structured Parameter Initialization"*.
The valid pipeline (paper Fig. 1) is:

`JSON problem → ProblemGenerator → QUBOGenerator1.generate_IBMQ_QUBO_for_left_deep_trees_v2 (native (R+P)(J-1) encoding, §3.1)
→ spiq_initialization.py (clapton Clifford GA, §3.2) → IBMQExperiments.py (QAOA, COBYLA, statevector/Qasm sim, random vs SPIQ init)
→ newTemp.py + Postprocessing/Postprocessing1.readout (score vector + fallback, §3.3) → visualization.rmd (Table 1, Figs 3–5)`

Everything else is upstream SIGMOD'23 code, abandoned experiments, or copy-pasted variants. User decisions:
**remove upstream entirely**, **clapton/: docs only**, **scrub secrets from config.py**.

## 1. Delete (verify with `grep -r` for references before each `git rm`)
**Upstream SIGMOD'23:** `base/DWaveExperiments.py`, `base/DWaveExperimentsDeprecated.py`, `base/TranspilationExperiment.py`,
`base/Scripts/{QUBOGenerator.py (MILP/slack encoding + gurobi), CircuitGeneration.py, TopologyGenerator.py, SteinbrunnQueryGenerator.py}`,
data dirs `base/TranspilationExperiment/` (~19k files), `base/couplings/`, `base/ExperimentalAnalysis/DWave/`,
`base/ExperimentalAnalysis/IBMQ/Embeddings/`, root `ExperimentalAnalysis/`, `docs/`, `Quantum_Foundations.pdf`, `licenses/`,
`scripts/plotting/*.r`, `scripts/run_dwave.sh`, `scripts/run_codesign.sh`, `scripts/run_all.sh`.

**Dead / superseded in our own work:**
- `base/Temp.py` — byte-identical to `newTemp.py` except the hard-coded week dir.
- `base/NewPostProcessing.py` — older CLI variant of newTemp (Week23 paths, no trial subdir).
- `base/GetFull.py` (I/O page-cost model, not in paper), `base/maxcut.py` (toy), `base/performance.py` (calls non-existent `generate_join_ordering_problem_by_size`),
  `base/spiq.py` (never imported; needs a different qiskit stack), `base/spiq_initialize.ipynb` (superseded by `spiq_initialization.py`).
- `plot.rmd` (Mar-2026 1000-iteration plots, superseded by `visualization.rmd`).
- Tracked junk: all `.DS_Store`, `__pycache__/*.pyc`, root `test.txt trace.txt ising_hamiltonian.txt maxcut_hamiltonian.txt postprocess_output.txt readout_summary_*.csv`,
  `base/run_log.txt`, `base/energy_logs/`. Extend `.gitignore` (`__pycache__/ .DS_Store *.log venv/ spiq/ .serena/`).
- **Kept untouched:** result data in `outputs/`, `spiq_init_outputs/`, `new_spiq_outputs/`, `visualization.rmd/.pdf`, `Problems/JSON/*`.

## 2. Simplify live code (behavior-preserving unless noted)
**`base/Scripts/`**
- Rename `QUBOGenerator1.py → QUBOGenerator.py`; keep only `get_log_values` + `generate_IBMQ_QUBO_for_left_deep_trees_v2`
  (drop threshold/legacy/DWave/Fujitsu variants, slack helpers, `dimod` import).
- Merge `Postprocessing1.py` into `Postprocessing.py`. Keep: `readout`, `get_raw_join_order`, `postprocess_join_order` (fallback),
  cost helpers used by them, `postprocess_qiskit_with_readout`. Drop: `postprocess_IBMQ_response`/`get_join_tree_leaves`/threshold-cost/
  `brute_force_JO` (they decode the *old* MILP variable layout, wrong for the v2 encoding), `postprocess_DWave_response`,
  broken `callBackEnergy` (undefined `response`), unused `write_bitstring_energy_prob`, bushy-tree helpers, module-level globals.
  Extract one `write_readout_csv(path, best_for_time, all_solutions)` used by both readout writers (currently copy-pasted).
- `ProblemGenerator.py`: keep `get_join_ordering_problem` (file-based branch) + `load_from_path` + `format_loaded_pred`; drop QUBO pickling,
  Trummer-generator branch, Auckland problem table, `QUBOGenerator` import. Update 3 call sites (drop `generated_problems=False`).

**`base/IBMQExperiments.py`**
- Remove transpilation/depth code and its imports (`conduct_IBMQ_transpilation_experiments`, `parse_transpilation_data`, gateset getters,
  `save_results/load_result/save_to_csv/process_data/parse_QPU_data`, `get_IBMQ_QASM_backend`, `print("COndu")`).
- `solve_with_QAOA`: remove duplicated ising-offset block and duplicated callback lines, dead `_run_checkpoint`/`_ensure_header`/
  `checkpoint_every`, unused `get_optimal_join_order` call, unused `card/pred/pred_sel/thres/inputNumber` params (and `thres` dict), commented code.
  Random-init baseline becomes `initial_point = [0.5] * (2 * reps)` — identical for the paper's reps=2; **fixes** reps=3 (was a length-4 point → crash); reps=1 changes 0.0→0.5.
- `solve_with_QAOA_spiq`: drop unused params/commented block; share one `_counts_to_samples(counts, qubo)` helper (the bit-reverse +
  `qubo.objective.evaluate` loop is copy-pasted 4×) between both solvers and `_evaluate_expected_qubo_energy`; drop the no-op `evaluate(list(x))` fallback.
- QPU branch: replace ad-hoc `BufSample/BufResponse` classes with existing `_make_spiq_sample/_make_spiq_response`; pass `result_dir` (was writing to `./9/...`).
- CLI: add `--week` (default `Week84`, replaces hard-coded `currentWeek`) and `--iterations` (default 10000). Remove Jupyter `# In[n]` markers.
- `config.py`: keep only `ibmq-*` keys; token via `os.environ.get("IBMQ_TOKEN", "")`. Gurobi WLS id/secret/license deleted (no longer used) —
  **they remain in git history; rotate them.**

**`base/newTemp.py` → `base/postprocess_results.py`**: drop `parse_QPU_data`, unused imports/`thre`, `PS1` parameter plumbing;
argparse `--trial (nargs+) --reps --optimizer --input_idx --iterations --week --evals (default 1)` replacing hard-coded Week4 path and loop.
Keep the ground-state printout.

**`base/spiq_initialization.py`**: remove duplicate import; otherwise unchanged logic.

**Scripts/Docker/deps**: `scripts/run.sh` options → `ibmq|bash`; `run_ibmq.sh` strip ~70 lines of commented runs.
Dockerfile: drop Gurobi download/env. `requirements.txt`: drop pytket*, pyquil, pydantic, iteration_utilities, dimod, dwave-*, networkx,
qubovert, gurobipy, multiprocess*, sympy (verify each with grep). Add `requirements-spiq.txt` for the separate SPIQ env from
`spiq/bin/python -m pip freeze`, trimmed to direct deps (qiskit-aer 0.13.3, qiskit-algorithms 0.3.1, stim, pygad, psutil, …); README currently points to a non-existent `install.txt`.

## 3. Documentation
- Module docstring on every live Python file stating its role in paper Fig. 1 and section (§3.1/§3.2/§3.3/§5).
- Docstrings (args/returns/scale: Ising vs QUBO energy) on every live function lacking one; inline comments on non-obvious lines
  (variable layout `v[t,j]`/`pred_vars[p,j]`, H_A/H_B/H_pred/H_cost, bit-order reversal, Ising offset, score vector/weight vector, fallback traversal, why relaxed θ = kπ/2).
- `clapton/`: module docstrings (provenance: CAFQA/SPIQ, Bharadwaj et al. 2026) + docstrings on functions SPIQ calls
  (`modify_circuit`, `transform_to_allowed_gates`, `relax_qaoa_parameters`, `qiskit_to_stim`, `generate_qiskit_param_map`, `claptonize`,
  `GateGeneralDepolarizationModel`). No code changes.
- README rewrite: paper title/citation/link, Fig. 1 pipeline with real filenames, the two environments, paper problems P1–P3
  (card/pred/sel, qubits 6/12/20) and how to select them, step-by-step run (SPIQ → QAOA random vs SPIQ → postprocess → visualization.rmd),
  output layout, metrics (cost ratio / optimal ratio / energy convergence, fallback on/off) mapped to Table 1 & Figs 3–5. Drop the upstream reproduction section.

## 4. Verification
1. Before editing, capture baselines from the current code (in `venv/`): `qubo.export_as_lp_string()` for inputs `0_predicates`, `03_predicates`,
   a 3-rel problem; and `PS1.readout(...)` output on a fixed synthetic sample list.
2. After: `python -m py_compile` on all remaining `.py`; grep for any import of deleted modules/names.
3. LP strings identical; `readout` output identical except `time_ms`.
4. SPIQ smoke (in `spiq/` venv): `cd base && python spiq_initialization.py --input_idx 0 --reps 2 --n_gens 20 --n_proc 4 --out_dir <scratch>` → JSON keys match an existing `spiq_init_outputs/*.json`.
5. QAOA smoke (in `venv/`): `python IBMQExperiments.py --trial 99 --reps 2 --optimizer 1 --iterations 5 --week <scratch>` with and without `--spiq_json`;
   check `energy_per_iteration_*.csv`, `min_state_readout.csv`, pickle written with the same schema as committed outputs.
6. `python base/postprocess_results.py --trial 99 --reps 2 --optimizer 1 --input_idx 0 --iterations 5 --week <scratch>` → `readout_summary*.csv` header matches committed ones.
7. No commit unless asked.
