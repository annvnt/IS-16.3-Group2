"""Schedule evaluation: cycle time (Phase 3 objective) and simulated makespan."""

from __future__ import annotations

from .models import Allocation
from .timeline import build_timeline


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
    """Return the makespan of one MPS pass under ``sequence``.

    The true objective optimized by IG-LS. Derived from the shared schedule
    timeline (see :func:`ffll_igls.timeline.build_timeline`).

    Args:
        sequence: A job release order.
        alloc: The Phase 1 allocation.

    Returns:
        The completion time of the last job to leave the system.
    """
    operations = build_timeline(sequence, alloc)
    return float(max((op.finish for op in operations), default=0.0))
