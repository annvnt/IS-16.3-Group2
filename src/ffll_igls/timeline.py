"""Build the detailed start/finish timeline of a schedule (basis for Gantt charts)."""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from .models import Allocation


class Operation(NamedTuple):
    """One job's processing step at one stage.

    Attributes:
        job: Job index (0-based).
        stage: Stage index (0-based).
        machine: Global machine index that runs the operation.
        start: Start time.
        finish: Finish time (``start + processing time``).
    """

    job: int
    stage: int
    machine: int
    start: float
    finish: float


def build_timeline(sequence: list[int], alloc: Allocation) -> list[Operation]:
    """Simulate one MPS pass and return every operation with its timing.

    Jobs flow stage by stage in ``sequence`` order; each machine serves jobs in
    arrival order. Bypassed stages produce no operation. This is the shared
    schedule simulation: :func:`ffll_igls.simulation.simulate_makespan` derives
    the makespan from it, and the Gantt charts draw it directly.

    Args:
        sequence: A job release order.
        alloc: The Phase 1 allocation.

    Returns:
        The operations in the order they are scheduled.
    """
    operations: list[Operation] = []
    job_ready = np.zeros(alloc.p.shape[1])

    for stage, machines in enumerate(_machines_by_stage(alloc.machine_stage)):
        machine_free = {machine: 0.0 for machine in machines}
        for job in sequence:
            machine = _assigned_machine(alloc.p, machines, job)
            if machine is None:
                continue  # bypass: no operation at this stage
            start = max(job_ready[job], machine_free[machine])
            finish = start + alloc.p[machine, job]
            operations.append(Operation(job, stage, machine, float(start), float(finish)))
            machine_free[machine] = finish
            job_ready[job] = finish

    return operations


def _machines_by_stage(machine_stage: list[int]) -> list[list[int]]:
    """Group global machine indices by their stage."""
    groups: list[list[int]] = [[] for _ in range(max(machine_stage) + 1)]
    for machine, stage in enumerate(machine_stage):
        groups[stage].append(machine)
    return groups


def _assigned_machine(p: np.ndarray, machines: list[int], job: int) -> int | None:
    """Return the stage machine processing ``job``, or None if it bypasses the stage."""
    for machine in machines:
        if p[machine, job] > 0:
            return machine
    return None
