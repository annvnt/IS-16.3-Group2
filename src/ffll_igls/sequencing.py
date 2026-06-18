"""Phase 2 of FFLL: order job releases via the Dynamic Balancing heuristic."""

from __future__ import annotations

import numpy as np

from .models import Allocation


def dynamic_balancing(alloc: Allocation) -> list[int]:
    """Greedily order jobs to minimize cumulative positive overload.

    Implements FFLL Phase 2: at each position, pick the unscheduled job that
    yields the lowest total positive cumulative overload.

    Args:
        alloc: The Phase 1 allocation.

    Returns:
        The job release sequence as a list of job indices.
    """
    overload = _overload_matrix(alloc)
    cumulative = np.zeros(overload.shape[0])
    remaining = list(range(overload.shape[1]))
    sequence: list[int] = []

    while remaining:
        best_job = min(
            remaining,
            key=lambda job: np.maximum(cumulative + overload[:, job], 0).sum(),
        )
        sequence.append(best_job)
        remaining.remove(best_job)
        cumulative += overload[:, best_job]

    return sequence


def overload_score(sequence: list[int], alloc: Allocation) -> float:
    """Return the total positive cumulative overload of a sequence (Phase 2 objective).

    Args:
        sequence: A job release order.
        alloc: The Phase 1 allocation.

    Returns:
        ``sum over machines and positions of max(cumulative_overload, 0)``.
    """
    overload = _overload_matrix(alloc)
    cumulative = np.zeros(overload.shape[0])
    score = 0.0
    for job in sequence:
        cumulative += overload[:, job]
        score += np.maximum(cumulative, 0).sum()
    return float(score)


def _overload_matrix(alloc: Allocation) -> np.ndarray:
    """Return per-job overload vectors ``O[:, j] = p_ij - p_j * W_i / W_total``.

    Column ``j`` is how much job ``j`` overloads each machine relative to that
    machine's fair share of the total system workload.
    """
    total_workload = alloc.W.sum()
    if total_workload == 0:
        return np.zeros_like(alloc.p)
    job_workloads = alloc.p.sum(axis=0)  # p_j: total system load of each job
    return alloc.p - np.outer(alloc.W, job_workloads) / total_workload
