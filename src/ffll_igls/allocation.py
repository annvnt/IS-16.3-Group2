"""Phase 1 of FFLL: assign each job to one machine per stage (LPT heuristic)."""

from __future__ import annotations

import numpy as np

from .models import Allocation, Instance


def allocate_machines(inst: Instance) -> Allocation:
    """Assign each job to one machine per stage to balance workloads.

    Implements FFLL Phase 1: the Longest Processing Time (LPT) rule is applied
    independently at every stage that has parallel machines.

    Args:
        inst: The scheduling instance.

    Returns:
        The full per-machine allocation (processing matrix, stage map, workloads).
    """
    p = np.zeros((inst.total_machines, inst.n_jobs))
    machine_stage: list[int] = []
    first_machine = 0

    for stage in range(inst.stages):
        n_machines = inst.machines_per_stage[stage]
        machine_indices = list(range(first_machine, first_machine + n_machines))
        machine_stage.extend([stage] * n_machines)
        _assign_stage_lpt(p, inst.stage_times[stage], machine_indices)
        first_machine += n_machines

    return Allocation(p=p, machine_stage=machine_stage, W=p.sum(axis=1))


def _assign_stage_lpt(
    p: np.ndarray, stage_times: np.ndarray, machine_indices: list[int]
) -> None:
    """Place each non-bypassing job of one stage onto its least-loaded machine.

    Jobs are considered in decreasing processing time (LPT). Mutates ``p`` in place.
    """
    if len(machine_indices) == 1:
        p[machine_indices[0], :] = stage_times
        return

    loads = {machine: 0.0 for machine in machine_indices}
    for job in np.argsort(-stage_times):  # descending processing time
        if stage_times[job] == 0:
            continue  # bypass: leave p[·, job] = 0
        target = min(loads, key=loads.get)
        p[target, job] = stage_times[job]
        loads[target] += stage_times[job]
