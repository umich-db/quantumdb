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

Older runs are all filed under `input0` whatever the problem, so they're identified here by qubit and parameter count.

## Multi-start runs (`outputs/multi-spiq/energy/WeekNN` = energy logs, `outputs/multi-spiq/WeekNN` = postprocessed readouts)

| Week | Problem | Method | Notes |
|---|---|---|---|
| Week90 | P1 | Single-start SPIQ | 835 evals, min energy 1.544 |
| Week91 | P2 | Multi-start SPIQ: 10 candidates exported, 3 starts, winner start0 | min 8.254. Per-start logs are `_start{0,1,2}.csv`. The readouts' first line is a `#` run note |
| Week92 | P3 | Multi-start SPIQ: 10 candidates exported, 3 starts, winner start1 | min 12.825 (the starts reached 13.52 / 12.82 / 13.20). The readouts' first line is a `#` run note |
| Week93 | P1 | **Diverse** multi-start SPIQ, **1000 iterations** | min **1.125** (exact 1.031). SPIQ best Ising -2.935. Starts reached 1.125 / 1.662 / 1.544; winner start0 |
| Week94 | P2 | **Diverse** multi-start SPIQ, **1000 iterations** | min **5.550** (exact 4.766). SPIQ best Ising -14.918. Starts reached 5.550 / 8.166 / 8.280; winner start0 |
| Week95 | P3 | **Diverse** multi-start SPIQ, **1000 iterations** | min **12.373** (exact 2.725). SPIQ best Ising -13.372. Starts reached 12.373 / 14.923 / 12.515; winner start0 |

Week93–95 settings: 8 independent GAs (`--n_starts 8`), seed 0, `--n_gens 2000`,
`--energy_window 0.25`, `--n_candidates 10`, `--spiq_starts 3`, COBYLA with 1000
iterations, reps 2, trial 1. Their files are under `iterations_1000/…` with the name
`energy_per_iteration_1000_COBYLA_2_1*.csv`, not `iterations_10000`. SPIQ outputs
are in `spiq_init_outputs/diverse_WeekNN/`, and the run logs in `logs/diverse_WeekNN_inputN.log`.

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

## Plots in `graphs/multi-spiq.rmd` (`plot_energy_comparison`)

| Plot | Random | Single-start SPIQ | Multi-start SPIQ | Reference |
|---|---|---|---|---|
| P1 | uninitialized/Week71 (4 qubits, **not P1**) | multi-spiq/Week90 | — | 1.031 |
| P2 | uninitialized/Week74/Week84 | spiq/Week88 | multi-spiq/Week91 | 4.766 |
| P3 | uninitialized/Week24 (Ising scale; plotted with `random_offset` = 25.80) | spiq/Week60 (better start point) | multi-spiq/Week92 | 2.725 |

`graphs/seeded-multi-spiq.rmd` uses the same random and single-start baselines. Its multi-start curve is the seeded, diverse run: P1 = multi-spiq/Week93 (single-start baseline multi-spiq/Week90), P2 = multi-spiq/Week94, P3 = multi-spiq/Week95. Those runs used 1000 iterations, so their files are under `iterations_1000`.

P1's random baseline is a different problem. P3's random baseline is plotted with +25.80 (the Ising offset) to put it on the same scale. P3's SPIQ runs share the same QUBO and circuit but start from different Clifford points (Week60: 9.87, Week92: 13.87), so they differ because of the starting point, not the method.
