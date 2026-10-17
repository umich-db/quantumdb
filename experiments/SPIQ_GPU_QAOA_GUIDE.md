# Running SPIQ + QAOA with GPU Acceleration

This guide explains how to run SPIQ-initialized QAOA with NVIDIA GPU acceleration. Given a supported join-ordering input, the code builds its QUBO, uses SPIQ to initialize a QAOA circuit whose gates have independent parameters, and then refines those parameters with GPU statevector simulation.

## 1. Why use a GPU?

After SPIQ produces an initial point, the QAOA optimizer repeatedly performs the same expensive operation: simulate the parameterized quantum circuit and calculate the expected value of the QUBO Hamiltonian. An exact statevector contains `2^Q` complex amplitudes, and COBYLA may request hundreds or thousands of objective evaluations. Statevector evaluation therefore becomes the main computational cost of the QAOA refinement stage as the qubit count grows.

GPUs are well suited to this workload because they can process many amplitudes in parallel. The current SPIQ implementation, by contrast, uses Stim's Clifford/stabilizer representation and a CPU genetic search. Moving SPIQ itself to a GPU would require a separate custom GPU stabilizer implementation and is not the simplest or most useful first integration point.

We benchmarked CPU and GPU exact-statevector evaluation on the same RTX 5080 machine. These are unpublished local measurements, included as implementation evidence rather than as a portable hardware claim. For a 20-qubit problem with 268 independently parameterized circuit angles:

- In the short benchmark, mean objective latency decreased from 1.673 seconds on CPU to 0.103 seconds on GPU: a 16.2x speedup.
- Over a complete 2,401-call budget, objective-evaluation time decreased from 1,524.5 seconds (25.41 minutes) to 185.6 seconds (3.09 minutes): an 8.2x speedup.

These numbers measure **QAOA objective-evaluation speedup**, not end-to-end SPIQ-plus-QAOA pipeline speedup. CPU-SPIQ preprocessing, COBYLA control logic, and database-plan decoding are not included. For small 5- or 12-qubit circuits, GPU launch overhead can dominate, so a GPU may provide little or no benefit.

The implemented data flow is:

```text
JOO input JSON
    |
    | CPU: SPIQ / Stim / Clifford search
    v
SPIQ JSON bundle + per-gate-parameterized circuit QPY
    |
    | GPU: Aer exact-statevector expectation for each QAOA objective call
    | CPU: COBYLA chooses the next parameter vector
    v
optimized parameters + QUBO-energy history
    |
    | optional: exact-state reconstruction and database-plan decoding
    v
JOO metrics
```

The accurate description is therefore **GPU-accelerated QAOA refinement after CPU-SPIQ initialization**, not “GPU SPIQ.”

## 2. Available implementation choices and why we chose Qiskit Aer GPU

We considered four practical implementation paths:

| Option | Accelerated stage | Advantages | Main costs and limitations |
|---|---|---|---|
| **Qiskit Aer GPU exact statevector — selected** | QAOA objective evaluation after SPIQ | Change Aer's device to `GPU`; directly reuse the existing QPY circuit, Hamiltonian, and parameter order; CPU and GPU use the same interface; already benchmarked on the target workload | Requires NVIDIA/CUDA; memory grows as `2^Q`; small circuits may not benefit |
| Custom CUDA/cuStateVec or another GPU simulator | QAOA objective evaluation | More control over kernels, batching, and memory | Requires rewriting and revalidating the simulator/expectation interface, bit ordering, offsets, and numerical behavior |
| GPU tensor-network simulator | Some structured or low-entanglement QAOA circuits | May handle qubit counts beyond dense-statevector memory limits | Performance depends strongly on circuit structure and may not suit a circuit with independently parameterized gates; results are less directly comparable to the existing benchmark |
| Custom GPU stabilizer implementation | SPIQ initialization | Could potentially accelerate SPIQ itself | The project has no validated drop-in GPU replacement for Stim; it would require a substantial new implementation and validation effort |

We selected **Qiskit Aer GPU** for three reasons:

1. **Simple integration.** The QAOA circuit, its per-gate parameters, the QUBO Hamiltonian, and the COBYLA optimizer remain unchanged. The essential change is selecting the GPU backend.
2. **Controlled comparability.** CPU and GPU use the same Aer `EstimatorV2`, exact-statevector method, double precision, and Ising offset. We can evaluate the same initial point on both backends and verify numerical agreement.
3. **Measured evidence.** The 20-qubit workload showed an 8.2x reduction in total objective-evaluation time. The choice is supported by an end-to-end objective benchmark rather than theoretical GPU throughput alone.

For another SPIQ + QAOA project, we recommend starting with Aer GPU as the minimum-change baseline and running a 5–10-call pilot on the largest intended circuit. Consider a tensor-network or custom CUDA implementation only after memory or circuit structure becomes a demonstrated bottleneck.

## 3. Why two Python environments are used

The SPIQ and Aer-GPU components use separate tested dependency sets:

- CPU-SPIQ environment: Qiskit 0.45.3, Qiskit Aer 0.13.3, Qiskit Algorithms 0.3.1, Qiskit Optimization 0.6.1, Stim 1.16.0, PyGAD 3.3.1, and NumPy 1.26.4.
- GPU-QAOA environment: Qiskit 1.3.2, `qiskit-aer-gpu` 0.15.1, Qiskit Optimization 0.6.1, NumPy 1.26.4, and SciPy 1.14.1.

Do not install `qiskit-aer-gpu` over the Aer package in the SPIQ environment. The stable interface between the environments is a pair of files: the CPU environment writes a JSON bundle and QPY circuit, and the GPU environment reads them.

Each user should create two virtual environments inside their own clone or worktree. The following variables contain no user- or machine-specific absolute paths:

```bash
cd /path/to/your/quantumdb
REPO="$(git rev-parse --show-toplevel)"
CPU_PY="${SPIQ_PYTHON:-$REPO/.venv-spiq/bin/python}"
GPU_PY="${GPU_PYTHON:-$REPO/.venv-gpu/bin/python}"
```

If an environment is stored outside the repository, override the corresponding variable before running, for example `export SPIQ_PYTHON=/path/to/spiq/python`. Do not embed one developer's absolute paths in shared scripts or result metadata.

Create the CPU-SPIQ and GPU-QAOA environments from the repository root with:

```bash
python3.10 -m venv .venv-spiq
.venv-spiq/bin/pip install --upgrade pip
.venv-spiq/bin/pip install -r requirements-spiq.txt

python3.10 -m venv .venv-gpu
.venv-gpu/bin/pip install --upgrade pip
.venv-gpu/bin/pip install -r requirements-gpu.txt
```

Build the CPU-SPIQ environment from `requirements-spiq.txt` and verify that `stim`, `pygad`, and `qiskit` can be imported. Python 3.10 is recommended for the pinned dependency set.

## 4. Input format

A custom problem is a JSON file containing `card`, `pred`, and `pred_sel`:

```json
{
  "card": [10, 15, 20, 30],
  "pred": [[0, 1], [1, 2], [2, 3]],
  "pred_sel": [0.1, 0.1, 0.1]
}
```

- `card[i]` is the positive cardinality of relation `i`.
- `pred[j] = [u, v]` gives the relation endpoints of predicate `j`.
- `pred_sel[j]` is the selectivity corresponding to predicate `j`, in `(0, 1]`.
- Parallel predicates must remain separate entries unless a different QUBO formulation explicitly combines them.

## 5. Preflight checks

Confirm that the operating system can see the NVIDIA GPU:

```bash
nvidia-smi
```

Then verify that the installed Aer wheel exposes a GPU device:

```bash
"$GPU_PY" - <<'PY'
from qiskit_aer import AerSimulator
devices = tuple(AerSimulator().available_devices())
print("Aer devices:", devices)
assert "GPU" in devices, "Qiskit Aer does not report a GPU device"
print("GPU_READY=true")
PY
```

The output must include:

```text
Aer devices: ('CPU', 'GPU')
GPU_READY=true
```

Successful `nvidia-smi` output alone does not prove that Aer GPU is available. `AerSimulator().available_devices()` is the definitive application-level check.

Verify the CPU-SPIQ entry point and imports:

```bash
$CPU_PY -c 'import stim, pygad, qiskit; print("SPIQ imports OK")'
PYTHONPATH="$PWD/base:$PWD" $CPU_PY base/spiq_initialization.py --help
```

## 6. Step one: generate a SPIQ initialization on CPU

The following example uses `p=2`, a fixed seed, and four CPU worker processes:

```bash
cd /path/to/your/quantumdb
REPO="$(git rev-parse --show-toplevel)"
CPU_PY="${SPIQ_PYTHON:-$REPO/.venv-spiq/bin/python}"
GPU_PY="${GPU_PYTHON:-$REPO/.venv-gpu/bin/python}"
OUT="$REPO/experiments/results/my_spiq_qaoa_run"
mkdir -p "$OUT/spiq"

cd "$REPO"
PYTHONPATH="$REPO/base:$REPO" "$CPU_PY" base/spiq_initialization.py \
  --problem-json /path/to/problem.json \
  --label example \
  --reps 2 \
  --n_gens 200 \
  --n_proc 4 \
  --n_starts 4 \
  --n_rounds 1 \
  --seed 20261017 \
  --skip-exact-ground-state \
  --out_dir "$OUT/spiq"
```

The main outputs are:

```text
$OUT/spiq/spiq_initial_point_example_reps2_4rel_3pred.json
$OUT/spiq/spiq_pcirc_example_reps2_4rel_3pred.qpy
$OUT/spiq/spiq_trace_example_reps2_4rel_3pred.txt
```

The JSON field named `relaxed_initial_point` is the code-level name for the per-gate initial parameter vector. It is ordered exactly like `pcirc.parameters` in the QPY circuit. Treat the JSON and QPY as one inseparable bundle. Do not copy only the numerical vector and reconstruct a circuit that merely appears equivalent, and do not sort the parameters by name.

The GPU runner consumes the primary `relaxed_initial_point`. If SPIQ exports additional candidates in `relaxed_initial_points`, the runner does not select among or run them automatically; evaluating those points requires separate, explicitly identified runs.

`--skip-exact-ground-state` skips only the exponential reference ground-state calculation; it does not skip SPIQ. It is recommended for larger inputs. The default Qiskit statevector sanity check validates the SPIQ point. Use `--skip-statevector-verification` only when the problem is too large for CPU memory, and then perform the CPU/GPU initial-point validation described in Section 8.

## 7. Step two: run QAOA refinement on GPU

```bash
CUDA_VISIBLE_DEVICES=0 "$GPU_PY" experiments/gpu_qaoa_refinement.py \
  --spiq-json "$OUT/spiq/spiq_initial_point_example_reps2_4rel_3pred.json" \
  --qpy "$OUT/spiq/spiq_pcirc_example_reps2_4rel_3pred.qpy" \
  --device GPU \
  --initialization spiq \
  --maxiter 400 \
  --progress-every 50 \
  --output "$OUT/qaoa_gpu_spiq.json"
```

The essential implementation is:

```python
operator, offset = qubo.to_ising()
estimator = EstimatorV2(options={
    "default_precision": 0.0,
    "backend_options": {
        "method": "statevector",
        "device": "GPU",
        "precision": "double",
    },
})

result = estimator.run([(pcirc, operator, theta)]).result()
energy_qubo = float(result[0].data.evs) + float(offset)
```

The Ising `offset` must be added back to the expectation value to recover the original QUBO energy convention. Omitting it usually preserves rankings within one QUBO, but breaks numerical comparisons between CPU/GPU results, ground energies, and reports.

If the circuit is transpiled and receives a layout, map the observable to the same layout before evaluation. The generic project runner directly loads the saved QPY circuit and therefore does not perform another layout transformation.

### Evaluation-budget convention

- The explicit initialization evaluation is outside the optimizer-call budget.
- `--maxiter 400` gives SciPy COBYLA a maximum of 400 optimizer objective calls. COBYLA may terminate normally before reaching that limit.
- COBYLA's first objective call commonly reevaluates the initial point. Keep that call in the history.
- `objective_history_qubo[0]` is the explicit initialization evaluation; subsequent entries are optimizer calls.
- A budget checkpoint at `B` must use the cumulative-best-energy parameters observed within the first `B` optimizer calls. It must not use later parameters or select parameters by JOO quality.

The runner saves every evaluated parameter vector, its energy, and its evaluation time in call order. It also records the optimizer-returned point separately from the lowest-energy point observed in the trace.

## 8. Verify CPU/GPU equivalence at the initial point

Evaluate the same bundle once on each backend before optimization:

```bash
"$GPU_PY" experiments/gpu_qaoa_refinement.py \
  --spiq-json "$OUT/spiq/spiq_initial_point_example_reps2_4rel_3pred.json" \
  --qpy "$OUT/spiq/spiq_pcirc_example_reps2_4rel_3pred.qpy" \
  --device CPU --maxiter 0 --output "$OUT/initial_cpu.json"

CUDA_VISIBLE_DEVICES=0 "$GPU_PY" experiments/gpu_qaoa_refinement.py \
  --spiq-json "$OUT/spiq/spiq_initial_point_example_reps2_4rel_3pred.json" \
  --qpy "$OUT/spiq/spiq_pcirc_example_reps2_4rel_3pred.qpy" \
  --device GPU --maxiter 0 --output "$OUT/initial_gpu.json"

"$GPU_PY" - "$OUT/initial_cpu.json" "$OUT/initial_gpu.json" <<'PY'
import json, math, sys
cpu = json.load(open(sys.argv[1]))["initial_energy_qubo"]
gpu = json.load(open(sys.argv[2]))["initial_energy_qubo"]
print({"cpu": cpu, "gpu": gpu, "absolute_error": abs(cpu-gpu)})
assert math.isclose(cpu, gpu, rel_tol=1e-10, abs_tol=1e-9)
PY
```

The same SPIQ point should produce matching CPU and GPU initial energies within numerical precision. Later COBYLA trajectories may diverge because very small floating-point differences can alter optimizer decisions, so final parameters and final energies need not match bit for bit.

Bundles created before QPY hashes and parameter-name metadata were added can be loaded only with the explicit `--allow-unverified-qpy` option. Supply `--qpy` as well, verify the source manually, and do not use this compatibility path for newly generated bundles.

## 9. A controlled comparison with Random initialization

To study initialization effects, use exactly the same per-gate-parameterized QPY circuit, QUBO, depth, optimizer, budget, backend, and precision. Change only the initial vector:

```bash
CUDA_VISIBLE_DEVICES=0 "$GPU_PY" experiments/gpu_qaoa_refinement.py \
  --spiq-json "$OUT/spiq/spiq_initial_point_example_reps2_4rel_3pred.json" \
  --qpy "$OUT/spiq/spiq_pcirc_example_reps2_4rel_3pred.qpy" \
  --device GPU \
  --initialization random \
  --seed 20261018 \
  --maxiter 400 \
  --output "$OUT/qaoa_gpu_random.json"
```

This runner samples every gate parameter independently from `Uniform(0, 2*pi)`. Report SPIQ's CPU preprocessing time separately. Equal QAOA budgets do not imply equal end-to-end computational cost.

## 10. Resource and scale considerations

The theoretical lower bound for double-precision statevector amplitudes is approximately:

```text
16 * 2^Q bytes
```

Aer also needs memory for circuits, observables, workspace, and CUDA libraries. Do not fill GPU memory based only on the theoretical statevector size.

Recommended practice:

- Test the largest problem first with `--maxiter 0`, followed by a 5–10-call pilot.
- Run only one exact-statevector QAOA process on a GPU at a time.
- Record peak memory from `nvidia-smi` and objective latency.
- Expect GPU overhead to dominate on small circuits.
- A 27-qubit double-precision statevector needs about 2 GiB for amplitudes alone, but the complete job requires substantially more memory.
- A 45-qubit dense statevector is not feasible on the current 16 or 32 GiB class of GPU.

## 11. Minimum result and provenance record

The runner records the ordered objective trace and bundle hashes. For a publication-grade run, supplement that output with the remaining machine and repository provenance below:

- Problem JSON and hash.
- SPIQ JSON, QPY, and hashes.
- SPIQ seed, budget, and CPU runtime.
- QAOA parameter order, parameter count, and depth.
- Optimizer configuration, requested budget, actual objective calls, and stopping message.
- Initial parameters and initial energy.
- Every objective parameter vector, energy, and timing.
- Cumulative-best checkpoint parameters.
- GPU model, driver, Aer version, and precision.
- Git commit and dirty-worktree status.

Minimum validation checks are:

1. `len(relaxed_initial_point) == len(pcirc.parameters)`.
2. CPU and GPU initial energies agree.
3. Every energy uses the same QUBO convention and includes the Ising offset.
4. Any probability distribution sums to one.
5. SPIQ and Random paired runs differ only in initialization and SPIQ preprocessing.
6. Normal early termination is distinguished from reaching the maximum budget.

## 12. Official documentation and external benchmark references

The following sources support the implementation choice and provide broader performance context:

1. [Qiskit Aer simulator tutorial: GPU simulation and installation](https://qiskit.github.io/qiskit-aer/tutorials/1_aersimulator.html) documents the GPU-supported `statevector`, `density_matrix`, and `unitary` methods, the `device="GPU"` option, and the `qiskit-aer-gpu` package. It also notes the supported platform and CUDA requirements.
2. [IBM Quantum: exact and noisy simulation with Qiskit Aer primitives](https://quantum.cloud.ibm.com/docs/en/guides/simulate-with-qiskit-aer) describes Aer as a high-performance simulator and shows how Aer primitives are used for local circuit evaluation.
3. [Qiskit Aer: running with multiple GPUs and multiple nodes](https://qiskit.github.io/qiskit-aer/howtos/running_gpu.html) documents `blocking_enable`, `blocking_qubits`, MPI execution, and the memory constraint used to choose a chunk size.
4. [NVIDIA cuQuantum documentation: Qiskit integration](https://docs.nvidia.com/cuda/cuquantum/latest/appliance/qiskit.html) explains how the cuQuantum Appliance integrates a GPU statevector solver with the Qiskit Aer interface, including multi-GPU and multi-node execution.
5. [NVIDIA cuStateVec performance study](https://developer.nvidia.com/blog/accelerating-quantum-circuit-simulation-with-nvidia-custatevec/) reports single- and multi-GPU statevector benchmarks, including variational-algorithm workloads. It also explains why speedup generally increases with qubit count and why multi-GPU statevectors depend on interconnect bandwidth.
6. [NVIDIA cuQuantum benchmark suite](https://github.com/NVIDIA/cuQuantum/tree/main/benchmarks) provides reproducible circuit-level benchmark tooling, supports Qiskit frontends/backends, and records benchmark configuration and output as structured data.

These references establish that GPU statevector simulation is a supported and widely benchmarked approach. They do **not** predict the exact speedup of this JOO-QAOA workload. NVIDIA's published measurements use different GPUs, CPUs, circuits, simulators, and qubit counts. The 16.2x short-run and 8.2x full-run figures in this guide are measurements from our own QAOA circuit on an RTX 5080 and should be reported separately from the external results.

The linked Aer documentation may describe a newer release than the pinned `qiskit-aer-gpu==0.15.1` environment. Always verify the locally installed version with `AerSimulator().available_devices()` and a CPU/GPU same-state comparison before using benchmark results.

## 13. Code entry points and provenance

| File | Provenance |
|---|---|
| `base/spiq_initialization.py` | Based on `origin/spiq-joo` commit `6ab4dbbfad4feb4c070d4de1cf3a5d987af6f91e`. This workflow adds custom problem JSON input, input validation, portable QPY identity metadata, and optional expensive-validation controls without changing the upstream SPIQ search. |
| `experiments/gpu_qaoa_refinement.py` | Introduced by this GPU workflow; it is not present in upstream commit `6ab4dbbf...`. |
| `requirements-gpu.txt` | Defines the isolated Aer-GPU environment introduced by this workflow; it is not present in upstream commit `6ab4dbbf...`. |
| `requirements-spiq.txt` | Retains the upstream SPIQ dependencies while pinning their mutually compatible Qiskit and NumPy versions for clean installation. |

Commit `6ab4dbbfad4feb4c070d4de1cf3a5d987af6f91e` is the upstream `spiq-joo` base for this change; it does not contain the GPU runner or GPU requirements. Recipients must use the commit containing this guide and its implementation files.
