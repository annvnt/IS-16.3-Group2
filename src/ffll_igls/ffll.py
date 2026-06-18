"""The full FFLL heuristic: allocation -> sequencing -> timing."""

from __future__ import annotations

from .allocation import allocate_machines
from .models import Instance, Schedule
from .sequencing import dynamic_balancing
from .simulation import bottleneck_cycle_time, simulate_makespan


def ffll(inst: Instance) -> Schedule:
    """Run the three-phase Flexible Flow Line Loading heuristic.

    Phase 1 (LPT allocation), Phase 2 (Dynamic Balancing sequencing), Phase 3
    (bottleneck-anchored timing).

    Args:
        inst: The scheduling instance.

    Returns:
        The resulting schedule (sequence, cycle time, makespan).
    """
    alloc = allocate_machines(inst)
    sequence = dynamic_balancing(alloc)
    return Schedule(
        sequence=sequence,
        cycle_time=bottleneck_cycle_time(alloc),
        makespan=simulate_makespan(sequence, alloc),
    )
