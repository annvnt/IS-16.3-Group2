"""Console reporting for the experiment suite (the I/O layer, no computation)."""

from __future__ import annotations

import numpy as np

from .allocation import allocate_machines
from .experiments import InstanceResult
from .ffll import ffll
from .igls import IGLSConfig, igls
from .models import Instance

# Smallest improvement counted as "improved" in the summary line.
_IMPROVED_THRESHOLD = 1e-3


def print_experiment_report(results: list[InstanceResult]) -> None:
    """Print the comparison table and summary for a list of instance results."""
    _print_table(results)
    _print_summary(results)


def _print_table(results: list[InstanceResult]) -> None:
    """Print the per-instance FFLL-vs-IG-LS comparison table."""
    header = (
        f"{'#':>2}  {'Label':<28} {'Jobs':>4} {'Stg':>3} {'LB':>6} "
        f"{'FFLL_ms':>8} {'FFLL_gap':>9} {'FFLL_t':>7} "
        f"{'IGLS_ms':>8} {'IGLS_gap':>9} {'IGLS_t':>7} {'Improv':>7}"
    )
    print("=" * len(header))
    print("FFLL vs IG-LS — 10 Random Instances")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r.index:>2}  {r.label:<28} {r.n_jobs:>4} {r.n_stages:>3} "
            f"{r.lower_bound:>6.1f} "
            f"{r.ffll_makespan:>8.2f} {r.ffll_gap:>8.1f}% {r.ffll_seconds:>6.3f}s "
            f"{r.igls_makespan:>8.2f} {r.igls_gap:>8.1f}% {r.igls_seconds:>6.3f}s "
            f"{r.improvement:>6.1f}%"
        )
    print("=" * len(header))


def _print_summary(results: list[InstanceResult]) -> None:
    """Print aggregate gap and improvement statistics over all results."""
    ffll_gaps = [r.ffll_gap for r in results]
    igls_gaps = [r.igls_gap for r in results]
    improvements = [r.improvement for r in results]
    improved = sum(1 for x in improvements if x > _IMPROVED_THRESHOLD)

    print(f"\n{'SUMMARY':}")
    print(f"  FFLL avg gap to LB : {np.mean(ffll_gaps):6.2f}%  (max: {np.max(ffll_gaps):.2f}%)")
    print(f"  IG-LS avg gap to LB: {np.mean(igls_gaps):6.2f}%  (max: {np.max(igls_gaps):.2f}%)")
    print(f"  Avg improvement    : {np.mean(improvements):6.2f}%  (max: {np.max(improvements):.2f}%)")
    print(f"  Instances improved : {improved}/{len(results)}")


def trace_instance(inst: Instance, label: str = "") -> None:
    """Print a detailed step-by-step trace of FFLL and IG-LS on one instance."""
    print(f"\n{'─' * 60}")
    print(f"DETAILED TRACE: {label}")
    print(f"{'─' * 60}")
    print(f"Jobs: {inst.n_jobs}, Stages: {inst.stages}, "
          f"Machines/stage: {inst.machines_per_stage}")
    print("\nStage processing times (stage x job):")
    for stage in range(inst.stages):
        row = "  ".join(f"{int(inst.stage_times[stage, j]):3d}" for j in range(inst.n_jobs))
        print(f"  Stage {stage + 1}: [{row}]")

    alloc = allocate_machines(inst)
    bottleneck = alloc.W.max()
    print(f"\nAfter LPT allocation — workloads W_i: {alloc.W}")
    print(f"Bottleneck lower bound: {bottleneck:.2f}")

    ffll_schedule = ffll(inst)
    print(f"\nFFLL sequence  : {[j + 1 for j in ffll_schedule.sequence]}")
    print(f"FFLL makespan  : {ffll_schedule.makespan:.2f}")
    print(f"FFLL gap to LB : {100 * (ffll_schedule.makespan - bottleneck) / bottleneck:.1f}%")

    igls_schedule = igls(inst, IGLSConfig(seed=42))
    print(f"\nIG-LS sequence : {[j + 1 for j in igls_schedule.sequence]}")
    print(f"IG-LS makespan : {igls_schedule.makespan:.2f}")
    print(f"IG-LS gap to LB: {100 * (igls_schedule.makespan - bottleneck) / bottleneck:.1f}%")
    improvement = 100 * (ffll_schedule.makespan - igls_schedule.makespan) / ffll_schedule.makespan
    print(f"Improvement    : {improvement:.1f}%")
