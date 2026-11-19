# Circuit analysis: old ("q2o") vs new ("qaoa") formulation

This document looks at the quantum circuit itself:
- which gates it contains;
- how many of each, for P1–P5 and both formulations;
- the rules behind those counts;
- what happens when the circuit is compiled for real hardware.

The Hamiltonian is covered in `problem-formulation.md` §9.0, and depth vs layers in §9.6.

**Where the numbers come from.** `base/circuit_gate_report.py` builds every circuit and counts its gates. It doesn't simulate anything, and it runs in the `sigmod-repro` container. Results: `docs/hamiltonians/circuit_gates.json`, with 30 rows (5 workloads × 2 formulations × 1–3 layers).

**Notation:**
- R: number of tables.
- P: number of join conditions.
- J = R − 2: join steps that get bits.
- n: qubits.
- Z, ZZ: number of one-qubit and two-qubit Pauli terms in the Hamiltonian.
- p: QAOA layers (`reps`). All our runs use p = 2.

---

## 1. Three versions of the same circuit

The same QAOA circuit exists in three forms. Each one is a rewrite of the one before it.

| Version | What it is | Gate types |
|---|---|---|
| **Plain** | The textbook `QAOAAnsatz`, decomposed into basic gates | H, RX, RZ, CNOT |
| **SPIQ** (what our runs execute) | The plain circuit rewritten by SPIQ (`build_vanilla_spiq_objects`), with one angle per rotation. COBYLA and NFT tune this circuit. | S, SX (√X), RZ, CNOT |
| **Hardware** | The SPIQ circuit compiled for a 65-qubit IBM device (FakeBrooklyn, heavy-hex layout) at optimization level 3, best of 5 seeds | RZ, SX, X, CNOT, plus measurements |

How the plain gates turn into SPIQ gates:
- **H** (the starting superposition) becomes S · SX · S.
- **Cost-layer RZ(γ·c)** is kept: one per Z term, and one inside each CNOT–RZ–CNOT for a ZZ term.
- **Mixer RX(2β)** becomes S · SX · RZ(2β) · SX · RZ(5π/2).
- **CNOT** is unchanged.

I checked that the SPIQ circuits rebuilt here have exactly the same gate counts as the `spiq_pcirc_*.qpy` files saved by the runs:
- new formulation: Weeks 105–109;
- old formulation: Weeks 110–111.

So the tables below describe the circuits that were actually executed.

**One small inefficiency.** RZ(5π/2) is the same gate as S, up to a global phase. SPIQ's Clifford check only recognises angles between 0 and 2π, so it misses this one and leaves a fixed RZ in every mixer. That is n·p extra RZ gates with no parameter. On hardware it costs nothing, because RZ is applied virtually in software. It does make the SPIQ RZ count look larger than it is.

### How the SPIQ circuit differs from the plain circuit

Both circuits have the same structure: a starting superposition, then for each layer a cost block (one rotation per Z term, CNOT–RZ–CNOT per ZZ term) followed by a mixer (one rotation per qubit). They differ in three ways.

**1. The angles are free, not shared.** This is the main difference.
- **Plain QAOA** has 2 angles per layer:
  - γ, shared by every cost rotation in that layer (each scaled by its term's coefficient c);
  - β, shared by every mixer rotation.
- **SPIQ "relaxes" the circuit** (`relax_qaoa_parameters` in `clapton`): every rotation gets its own angle. A cost gate becomes RZ(c · γᵢ) with its own γᵢ, and a mixer gate becomes RZ(2βᵢ) with its own βᵢ.

| Angles at 2 layers | P1 | P2 | P3 | P4 | P5 |
|---|---|---|---|---|---|
| Plain (2 per layer), both formulations | 4 | 4 | 4 | 4 | 4 |
| SPIQ, new = (Z + ZZ + n) · p | 18 | 64 | 64 | 140 | 252 |
| SPIQ, old | 40 | 116 | 268 | 410 | 868 |

The plain circuit is a special case of the SPIQ circuit: tie all the γᵢ of a layer together, and all the βᵢ, and you get it back. So the SPIQ circuit can express everything the plain one can, and more. It is no longer strictly QAOA, because the angles don't follow the two-angles-per-layer schedule. It is closer to a hardware-style circuit that keeps QAOA's gate layout.

**2. A different gate set, chosen so a fast classical simulator can run it.** SPIQ finds its starting point with stim, a simulator that only handles Clifford gates. When every angle is a multiple of π/2, every rotation is a Clifford gate. So SPIQ rewrites the circuit in gates stim understands (`modify_circuit`, `transform_to_allowed_gates`):

| Plain gate | SPIQ version |
|---|---|
| H (starting superposition) | S · SX · S |
| RZ(c · γ) (cost) | RZ(c · γᵢ), with its own angle |
| RX(2β) (mixer) | S · SX · RZ(2βᵢ) · SX · RZ(5π/2) |
| CNOT | CNOT (unchanged) |

This rewrite doesn't change what the circuit computes, but it does change the counts, at 2 layers:

| | Plain | SPIQ |
|---|---|---|
| CNOTs | 2 · ZZ · p | the same |
| RZ | (Z + ZZ) · p | (Z + ZZ + 2n) · p, of which n · p are the fixed RZ(5π/2) |
| Other single-qubit gates | n · p RX, n H | n(1 + 2p) SX, n(2 + p) S |
| Total gates, P5 new | 588 | 828 |
| Depth, P1 / P5 new | 23 / 80 | 33 / 90 |

The extra depth is single-qubit gates only; the CNOT depth is the same.

**3. A different starting point.**
- **Plain QAOA** starts from fixed angles (all 0.5 in the random-initialization runs, Week96–101).
- **SPIQ** starts from a point its search found:
  - a genetic algorithm searches over angles of the form kᵢ · π/2;
  - stim scores each candidate quickly, because at those angles the circuit is all Clifford;
  - the best point becomes the starting angles, θᵢ = kᵢ · π/2 divided by the gate's coefficient.

  The SPIQ start is therefore a Clifford state, typically spread over only a few bitstrings: 4 for P4 (`bottleneck.md` §2).

**What this means for the runs:**
- **More freedom, harder search.** P4 has 140 free angles instead of 4. The circuit can reach more states, but the optimizer has far more directions to search. NFT needed about 3000 evaluations on P4 before it improved at all (`bottleneck.md` §3.2).
- **Why NFT suits it.** Each angle drives exactly one gate, so the energy as a function of any single angle is an exact sine curve. NFT fits that curve and jumps to its minimum. In the plain circuit, one γ drives many gates at once, so this isn't exact.
- **It doesn't change hardware cost.** The CNOT count is identical. Compiled for hardware, S, SX and RZ all become cheap single-qubit gates (RZ is applied in software), so the extra gates in the SPIQ version cost almost nothing.

---

## 2. Gate counts at 2 layers (the setting of every run)

### SPIQ circuit (what COBYLA and NFT optimize)

| Workload | Formulation | Qubits | RZ | SX | S | CNOT | Total | Depth | CNOT depth | Angles |
|---|---|---|---|---|---|---|---|---|---|---|
| P1 | new | 3 | 24 | 15 | 12 | 12 | 63 | 33 | 12 | 18 |
| P1 | old | 5 | 50 | 25 | 20 | 40 | 135 | 51 | 24 | 40 |
| P2 | new | 8 | 80 | 40 | 32 | 64 | 216 | 48 | 22 | 64 |
| P2 | old | 12 | 140 | 60 | 48 | 136 | 384 | 63 | 32 | 116 |
| P3 | new | 8 | 80 | 40 | 32 | 64 | 216 | 48 | 22 | 64 |
| P3 | old | 20 | 308 | 100 | 80 | 376 | 864 | 99 | 56 | 268 |
| P4 | new | 15 | 170 | 75 | 60 | 160 | 465 | 75 | 40 | 140 |
| P4 | old | 30 | 470 | 150 | 120 | 580 | 1320 | 117 | 68 | 410 |
| P5 | new | 24 | 300 | 120 | 96 | 312 | 828 | 90 | 50 | 252 |
| P5 | old | 52 | 972 | 260 | 208 | 1320 | 2760 | 150 | 90 | 868 |

The plain circuit has the same CNOTs. Its single-qubit gates are fewer and simpler: (Z + ZZ)·p RZ, n·p RX and n H. P5 new, for example, has 204 RZ, 48 RX and 24 H.

### Old ÷ new, SPIQ circuit

| Workload | Total gates | CNOTs | Depth | Share of gates that are CNOTs (new / old) |
|---|---|---|---|---|
| P1 | 2.1× | 3.3× | 1.6× | 19% / 30% |
| P2 | 1.8× | 2.1× | 1.3× | 30% / 35% |
| P3 | 4.0× | 5.9× | 2.1× | 30% / 44% |
| P4 | 2.8× | 3.6× | 1.6× | 34% / 44% |
| P5 | 3.3× | 4.2× | 1.7× | 38% / 48% |

The old formulation has more of every gate type. The gap is largest for CNOTs, which are the expensive gate. A bigger share of its gates are CNOTs too.

---

## 3. The rules behind the counts

The counts above follow exact formulas, checked on all 30 rows. Let **b** be the number of bits per join step:
- new: b = R (one bit per table);
- old: b = R + P (one bit per table and per condition).

**Hamiltonian:**
- n = b·J
- Z = n (every qubit has a Z term)
- ZZ = J·b(b−1)/2 + R(J−1)

**Plain circuit:**

| Gate | Count |
|---|---|
| CNOT | 2·ZZ·p |
| RZ | (Z + ZZ)·p |
| RX | n·p |
| H | n |

**SPIQ circuit:**

| Gate | Count |
|---|---|
| CNOT | 2·ZZ·p |
| RZ | (Z + ZZ + 2n)·p |
| S | n·(2 + p) |
| SX | n·(1 + 2p) |
| Angles | (Z + ZZ + n)·p |

In words:
- **CNOTs depend only on ZZ terms**, 2 per term per layer.
- **RZs track the number of terms**: one per Z or ZZ term per layer, plus 2 per qubit per layer from the mixer in the SPIQ version.
- **SX and S depend only on the number of qubits.**
- **Every gate count grows linearly with p.**

### Pattern by workload

**New formulation: the circuit depends only on the number of tables.** With b = R, nothing in the formulas involves P:

- CNOT = p · R · (J(R+1) − 2), about p·R³ when R is large.

That is why P2 (4 tables, 2 conditions) and P3 (4 tables, 6 conditions) have identical circuits gate for gate. Only the RZ angles differ. Adding join conditions to a query adds no gates in the new formulation. A condition between tables a and b becomes the term v_a·v_b, and penalty A already couples every pair of tables in the same step. So the condition only changes the size of a coupling that already exists.

**Old formulation: the circuit grows with tables and conditions.** With b = R + P:

- CNOT = p · (J·(R+P)(R+P−1) + 2R(J−1)).

Every condition adds J qubits, plus couplings to everything else in the same step, because the squared cost multiplies every pair of bits in a step. That is why:
- P3 old (6 conditions) has 2.8× the CNOTs of P2 old (2 conditions), with the same 4 tables;
- the old ÷ new ratio jumps at P3 (5.9×) and P5 (4.2×), the workloads with the most conditions.

| What changes | New formulation | Old formulation |
|---|---|---|
| Add one table (R → R+1) | Qubits go from R(R−2) to (R+1)(R−1); CNOTs grow about as R³ | Same, plus every condition gains another step's worth of bits |
| Add one condition (P → P+1) | **No change in gates** (only angles) | +J qubits, and about 2·J·(R+P)·p more CNOTs |
| Add one layer (p → p+1) | Every gate count grows by one layer's worth; H/initial gates are fixed | Same |

---

## 4. Compiled for real hardware

Real IBM devices don't connect every qubit to every other. On the heavy-hex layout each qubit has at most 3 neighbours. So the compiler inserts SWAPs, which are 3 CNOTs each, to bring coupled qubits next to each other.

The compile target is FakeBrooklyn: 65 qubits, heavy-hex, with its 2021 calibration (median CNOT error 1.0%, SX error 0.03%, readout error 2.4%). Optimization level 3, best of 5 seeds.

**ESP (estimated success probability)** is the product of (1 − error) over every gate and readout. It is a rough chance that the whole circuit runs with no error at all.

| Workload | Formulation | CNOTs before → after compiling | Overhead | Depth after compiling | ESP |
|---|---|---|---|---|---|
| P1 | new | 12 → 19 | 1.6× | 46 | **0.81** |
| P1 | old | 40 → 65 | 1.6× | 112 | 0.50 |
| P2 | new | 64 → 124 | 1.9× | 132 | **0.26** |
| P2 | old | 136 → 275 | 2.0× | 201 | 0.034 |
| P3 | new | 64 → 124 | 1.9× | 132 | **0.26** |
| P3 | old | 376 → 851 | 2.3× | 398 | 3 × 10⁻⁶ |
| P4 | new | 160 → 431 | 2.7× | 308 | 2 × 10⁻⁴ |
| P4 | old | 580 → 1435 | 2.5× | 635 | 1 × 10⁻¹⁰ |
| P5 | new | 312 → 871 | 2.8× | 340 | 4 × 10⁻⁷ |
| P5 | old | 1320 → 3648 | 2.8× | 1015 | 3 × 10⁻²¹ |

What this shows:
- **Compiling roughly doubles to triples the CNOT count in both formulations.** The overhead grows with size (1.6× → 2.8×) because the couplings in each step are all-to-all, and heavy-hex is far from that. The overhead is about the same for old and new, so the new formulation's advantage carries over to hardware: 2.2–6.9× fewer CNOTs and 1.5–3× less depth after compiling.
- **ESP falls off exponentially with CNOTs**, so a 2–7× gap in CNOTs becomes a huge gap in ESP:
  - P2: the new circuit is 8× more likely to run without error;
  - P3: 80,000×;
  - P5: about 10¹⁴×.
- **Only the new P1–P3 circuits are in a range where hardware runs could plausibly work** (ESP 0.26–0.81). The old circuit is already at 3 × 10⁻⁶ by P3. P4 and P5 are out of reach for both on this device, so hardware results there would mostly be noise without error mitigation.
- **These calibration numbers are from 2021.** Current IBM Heron devices have about 3× lower 2-qubit error. That shifts every ESP up but leaves the ranking unchanged.
- **The "CNOTs after compiling" counts are approximate.** Level-3 optimization also merges and cancels some gates, so the difference before and after isn't exactly 3 × SWAPs.

---

## 5. Is the new circuit better?

**As a circuit: yes, on every measure.**

| Measure | Old ÷ new |
|---|---|
| Qubits | 1.5–2.5× |
| Total gates | 1.8–4.0× |
| CNOTs, before compiling | 2.1–5.9× |
| CNOTs, after compiling | 2.2–6.9× |
| Depth after compiling | 1.5–3.0× |

The new circuit also has 1.8–4.2× fewer angles to tune, and a far higher chance of running without error.

The new circuit also scales better: its size is set by the number of tables alone, while the old one grows with every join condition as well.

**What "better circuit" doesn't mean.** A smaller circuit is cheaper and less noisy, but that doesn't guarantee the optimizer finds a good plan. That depends on the energy landscape, the starting point and the optimizer.
- The results so far (`RESULTS_INDEX.md`, "Findings") show the new formulation's ground state is the right plan, and P1/P3 start at it from SPIQ.
- P4/P5 barely move under COBYLA or NFT.

So the circuit is no longer what limits P4/P5. Training is. Section 6 lists ways to check why.

---

## 6. What else is worth analyzing

In rough order of value for the effort:

1. **Better gate ordering (cheap, no simulation).** The ZZ gates within a layer can run in parallel when they share no qubit. Grouping them that way (an edge colouring of the coupling graph) needs only about "most couplings on one qubit" rounds. Qiskit's default order is 1.5–2.5× worse than that (§9.6). Re-ordering the terms before building the circuit could cut depth by up to about 2× for free. A swap network (all-to-all coupling on a line of qubits in about n CNOT rounds) is the hardware version of the same idea. It suits this problem because each step's couplings are all-to-all.

2. **Noisy simulation of the new P1–P3 (in docker).** Run the same SPIQ + COBYLA/NFT pipeline with a noise model taken from a real device's error rates. Does the optimal ratio survive? That is the real test of whether the ESP gap in §4 matters. `clapton` already has `GateGeneralDepolarizationModel`, and Aer can load FakeBrooklyn's noise model.

3. **Why P4/P5 don't train: gradient size (barren plateaus).** At random angles, measure how much the energy changes when one angle changes (the variance of the gradient), for each qubit count. If it shrinks quickly from P3 to P5, the landscape is too flat, which would explain the flat COBYLA and NFT curves. This needs statevector simulation in docker; P5 new has 24 qubits, which is feasible.

4. **Fewer angles.** The SPIQ circuit has one angle per gate: 252 for P5 new, against 4 in plain QAOA at 2 layers. Try tying angles back together, for example one angle per penalty type or per join step, and see whether the optimizer does better with fewer knobs. This is a direct test of whether 250+ independent angles are part of why P4/P5 stall.

5. **How far the angles move from the SPIQ start.** The SPIQ start is a Clifford point (every angle a multiple of π/2). Compare the final angles with the start: if they barely move, the optimizer is stuck near the start rather than exploring.

6. **Light cones.** For each output qubit, count how many qubits can affect it after p layers. With the new formulation's all-to-all coupling inside each step, this probably covers the whole register by p = 2. That has consequences for both trainability and classical simulation.

7. **Fix the RZ(5π/2) miss in SPIQ (tiny).** Reduce angles modulo 2π before the Clifford check, so the extra mixer RZ becomes an S gate. It won't change results, but the gate counts will show the real structure.

---

## Reproduce

```bash
docker cp base/circuit_gate_report.py sigmod-repro:/home/repro/sigmod-repro/base/
docker exec -w /home/repro/sigmod-repro/base -e PYTHONPATH=/home/repro/spiq-site:/home/repro/sigmod-repro \
  sigmod-repro python3 circuit_gate_report.py
docker cp sigmod-repro:/home/repro/sigmod-repro/docs/hamiltonians/circuit_gates.json docs/hamiltonians/
```

It takes about 5 minutes; the hardware compile of P5 old is the slow part.
