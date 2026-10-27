#!/usr/bin/env python3
"""Refine a saved SPIQ point with Aer exact CPU/GPU expectation values.

The JSON and QPY bundle preserves the circuit and parameter order selected by
SPIQ while allowing QAOA refinement to run in a separate Aer environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from qiskit import qpy
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import EstimatorV2


def _repo_base() -> Path:
    return Path(__file__).resolve().parents[1] / "base"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_bundle(path: Path, qpy_path: str | None, allow_unverified_qpy: bool):
    bundle = json.loads(path.read_text())
    if qpy_path:
        # An explicit override follows normal CLI path semantics (the current
        # working directory), unlike a relative path recorded inside a bundle.
        circuit_path = Path(qpy_path).resolve()
    else:
        recorded = bundle.get("pcirc_qpy") or bundle.get("qpy_path")
        if recorded:
            recorded_path = Path(recorded)
            candidates = (
                [recorded_path]
                if recorded_path.is_absolute()
                else [
                    path.parent / recorded_path,
                    recorded_path,
                    path.parent / recorded_path.name,
                ]
            )
            circuit_path = next(
                (candidate.resolve() for candidate in candidates if candidate.exists()),
                (path.parent / recorded_path).resolve(),
            )
        else:
            circuit_path = path.with_name(
                path.name.replace("initial_point", "pcirc").replace(".json", ".qpy")
            )
    if not circuit_path.exists():
        raise FileNotFoundError(
            f"QPY circuit not found: {circuit_path}; pass --qpy explicitly"
        )

    expected_hash = bundle.get("pcirc_qpy_sha256")
    actual_hash = _sha256(circuit_path)
    if expected_hash is None and not allow_unverified_qpy:
        raise ValueError(
            "The SPIQ bundle does not contain pcirc_qpy_sha256; pass "
            "--allow-unverified-qpy only for a trusted legacy bundle"
        )
    if expected_hash is not None and actual_hash != expected_hash:
        raise ValueError(
            f"QPY SHA-256 mismatch: expected {expected_hash}, got {actual_hash}"
        )

    with circuit_path.open("rb") as handle:
        circuit = qpy.load(handle)[0]
    expected_names = bundle.get("relaxed_param_names")
    actual_names = [parameter.name for parameter in circuit.parameters]
    if expected_names is None:
        if not allow_unverified_qpy:
            raise ValueError("The SPIQ bundle does not record relaxed_param_names")
    elif expected_names != actual_names:
        raise ValueError("QPY parameter order does not match relaxed_param_names")
    return bundle, circuit, circuit_path, actual_hash


def _build_qubo(metadata: dict):
    # Preserve the exact JOO formulation while avoiding dependencies on the
    # legacy command-line driver and its input-directory conventions.
    import sys

    sys.path.insert(0, str(_repo_base()))
    import Scripts.QUBOGenerator as qubo_generator

    return qubo_generator.generate_IBMQ_QUBO_for_left_deep_trees_v2(
        metadata["card"], metadata["pred"], metadata["pred_sel"]
    )[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spiq-json", required=True, type=Path)
    parser.add_argument("--qpy", help="Override the QPY path recorded in the JSON")
    parser.add_argument(
        "--allow-unverified-qpy",
        action="store_true",
        help="Allow a trusted legacy bundle without complete QPY identity metadata.",
    )
    parser.add_argument("--device", choices=("CPU", "GPU"), default="GPU")
    parser.add_argument(
        "--initialization",
        choices=("spiq", "fixed", "random"),
        default="spiq",
        help="Starting point for the same relaxed circuit. 'fixed' uses --fixed-value.",
    )
    parser.add_argument(
        "--fixed-value",
        type=float,
        default=0.5,
        help="Per-gate value for --initialization fixed (default: 0.5).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Required seed recorded for --initialization random.",
    )
    parser.add_argument("--maxiter", type=int, default=200)
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Print an objective-timing update every N evaluations (0 disables).",
    )
    parser.add_argument("--output", type=Path, default=Path("gpu_qaoa_result.json"))
    args = parser.parse_args()

    if args.maxiter < 0:
        parser.error("--maxiter must be non-negative")
    if args.progress_every < 0:
        parser.error("--progress-every must be non-negative")

    bundle_path = args.spiq_json.resolve()
    bundle, pcirc, circuit_path, circuit_hash = _load_bundle(
        bundle_path,
        args.qpy,
        args.allow_unverified_qpy,
    )
    spiq_initial = np.asarray(bundle["relaxed_initial_point"], dtype=float)
    if len(spiq_initial) != len(pcirc.parameters):
        raise ValueError("SPIQ initial point does not match QPY parameter count")
    if args.initialization == "spiq":
        initial = spiq_initial
    elif args.initialization == "fixed":
        initial = np.full(len(pcirc.parameters), args.fixed_value, dtype=float)
    else:
        if args.seed is None:
            raise ValueError("--initialization random requires an explicit --seed")
        initial = np.random.default_rng(args.seed).uniform(
            0.0, 2.0 * np.pi, size=len(pcirc.parameters)
        )
    qubo = _build_qubo(bundle["problem_input"])
    operator, offset = qubo.to_ising()

    available = AerSimulator().available_devices()
    if args.device not in available:
        raise RuntimeError(
            f"Requested {args.device}, Aer reports available devices {available}"
        )
    backend_options = {
        "method": "statevector",
        "device": args.device,
        "precision": "double",
    }
    estimator = EstimatorV2(
        options={
            "default_precision": 0.0,
            "backend_options": backend_options,
        }
    )
    timings, history, parameter_history = [], [], []

    def energy(theta):
        start = time.perf_counter()
        parameters = np.asarray(theta, dtype=float)
        result = estimator.run([(pcirc, operator, parameters)]).result()
        value = float(np.asarray(result[0].data.evs).reshape(-1)[0]) + float(offset)
        timings.append(time.perf_counter() - start)
        history.append(value)
        parameter_history.append(parameters.tolist())
        if args.progress_every and len(history) % args.progress_every == 0:
            print(
                f"[progress] evaluations={len(history)} energy={value:.12f} "
                f"mean_seconds={np.mean(timings):.6f}",
                flush=True,
            )
        return value

    initial_energy = energy(initial)
    if args.maxiter:
        result = minimize(
            energy,
            initial,
            method="COBYLA",
            options={"maxiter": args.maxiter},
        )
        optimizer_result_energy = float(result.fun)
        optimizer_result_parameters = result.x.tolist()
        best_energy = optimizer_result_energy
        best_parameters = optimizer_result_parameters
        optimizer_success = bool(result.success)
        optimizer_message = str(result.message)
    else:
        # Evaluation-only mode avoids a redundant objective call from COBYLA.
        optimizer_result_energy = None
        optimizer_result_parameters = None
        best_energy = initial_energy
        best_parameters = initial.tolist()
        optimizer_success = None
        optimizer_message = "optimizer skipped (--maxiter 0)"

    trace_best_index = int(np.argmin(history))
    trace_best_energy = float(history[trace_best_index])
    trace_best_parameters = parameter_history[trace_best_index]
    payload = {
        "device": args.device,
        "spiq_json": str(bundle_path),
        "spiq_json_sha256": _sha256(bundle_path),
        "qpy": str(circuit_path),
        "qpy_sha256": circuit_hash,
        "qubits": pcirc.num_qubits,
        "parameters": len(pcirc.parameters),
        "parameter_names": [parameter.name for parameter in pcirc.parameters],
        "initial_parameters": initial.tolist(),
        "initial_energy_qubo": initial_energy,
        "ising_offset": float(offset),
        "initialization": args.initialization,
        "initialization_seed": args.seed,
        "fixed_value": args.fixed_value if args.initialization == "fixed" else None,
        "requested_optimizer_evaluations": args.maxiter,
        "optimizer_objective_evaluations": len(history) - 1,
        "explicit_initial_evaluations": 1,
        "best_energy_qubo": best_energy,
        "best_parameters": best_parameters,
        "trace_best_energy_qubo": trace_best_energy,
        "trace_best_evaluation_index": trace_best_index,
        "trace_best_parameters": trace_best_parameters,
        "evaluations": len(history),
        "first_evaluation_seconds": float(timings[0]),
        "mean_seconds_per_evaluation": float(np.mean(timings)),
        "median_seconds_per_evaluation": float(np.median(timings)),
        "total_seconds": float(np.sum(timings)),
        "optimizer_success": optimizer_success,
        "optimizer_message": optimizer_message,
        "optimizer_result_energy_qubo": optimizer_result_energy,
        "optimizer_result_parameters": optimizer_result_parameters,
        # Entry zero is the explicit initialization evaluation.
        "objective_history_qubo": [float(value) for value in history],
        "parameter_history": parameter_history,
        "evaluation_seconds": [float(value) for value in timings],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    verbose_fields = {
        "parameter_names",
        "initial_parameters",
        "best_parameters",
        "trace_best_parameters",
        "optimizer_result_parameters",
        "objective_history_qubo",
        "parameter_history",
        "evaluation_seconds",
    }
    printed_payload = {
        key: value for key, value in payload.items() if key not in verbose_fields
    }
    print(json.dumps(printed_payload, indent=2))


if __name__ == "__main__":
    main()
