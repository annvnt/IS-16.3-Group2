"""Schedule evaluation: cycle time (Phase 3 objective) and simulated makespan."""

from __future__ import annotations

import numpy as np

from .models import Allocation


def bottleneck_cycle_time(alloc: Allocation) -> float:
    """Return the cyclic cycle time = workload of the bottleneck machine.

    Implements FFLL Phase 3 (Bottleneck Anchoring): in steady state the cycle
    time of one MPS equals the highest per-machine workload.

    Args:
        alloc: The Phase 1 allocation.

    Returns:
        The bottleneck workload ``max_i W_i``.
    """
    return float(alloc.W.max())


def simulate_makespan(sequence: list[int], alloc: Allocation) -> float:
    """Simulate one MPS pass under ``sequence`` and return its makespan.

    Jobs flow stage by stage in ``sequence`` order; each machine serves jobs in
    arrival order. This is the true objective optimized by IG-LS.

    Args:
        sequence: A job release order.
        alloc: The Phase 1 allocation.

    Returns:
        The completion time of the last job to leave the system.
    """
    job_ready = np.zeros(alloc.p.shape[1])
    for machines in _machines_by_stage(alloc.machine_stage):
        job_ready = _advance_stage(alloc.p, machines, sequence, job_ready)
    return float(job_ready.max())


def _machines_by_stage(machine_stage: list[int]) -> list[list[int]]:
    """Group global machine indices by their stage."""
    groups: list[list[int]] = [[] for _ in range(max(machine_stage) + 1)]
    for machine, stage in enumerate(machine_stage):
        groups[stage].append(machine)
    return groups


def _advance_stage(
    p: np.ndarray, machines: list[int], sequence: list[int], job_ready: np.ndarray
) -> np.ndarray:
    """Return job completion times after one stage; jobs run in ``sequence`` order."""
    machine_free = {machine: 0.0 for machine in machines}
    next_ready = job_ready.copy()
    for job in sequence:
        machine = _assigned_machine(p, machines, job)
        if machine is None:
            continue  # bypass: completion time carries over unchanged
        start = max(job_ready[job], machine_free[machine])
        finish = start + p[machine, job]
        machine_free[machine] = finish
        next_ready[job] = finish
    return next_ready


def _assigned_machine(p: np.ndarray, machines: list[int], job: int) -> int | None:
    """Return the stage machine processing ``job``, or None if it bypasses the stage."""
    for machine in machines:
        if p[machine, job] > 0:
            return machine
    return None
