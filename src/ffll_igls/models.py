"""Core data structures shared across the FFLL / IG-LS pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np


@dataclass
class Instance:
    """One scheduling instance for a flexible flow line.

    Attributes:
        stages: Number of stages in series.
        machines_per_stage: Machine count at each stage (length ``stages``).
        n_jobs: Number of jobs in the Minimum Part Set (MPS).
        stage_times: ``(stages, n_jobs)`` matrix; entry ``[s, j]`` is the
            processing time of job ``j`` at stage ``s``. A ``0`` means job ``j``
            bypasses stage ``s``.
    """

    stages: int
    machines_per_stage: list[int]
    n_jobs: int
    stage_times: np.ndarray

    @property
    def total_machines(self) -> int:
        """Return the total number of machines across all stages."""
        return sum(self.machines_per_stage)


@dataclass
class Allocation:
    """Result of Phase 1: each job pinned to one machine per stage.

    Attributes:
        p: ``(total_machines, n_jobs)`` processing-time matrix after allocation.
        machine_stage: Maps a global machine index to its stage index.
        W: Workload (sum of processing times) per machine.
    """

    p: np.ndarray
    machine_stage: list[int]
    W: np.ndarray


class Schedule(NamedTuple):
    """A solved schedule. Tuple-compatible: ``seq, cycle_time, makespan = schedule``.

    Attributes:
        sequence: Job release order (0-based job indices).
        cycle_time: Cyclic cycle time of one MPS (bottleneck workload).
        makespan: Simulated makespan of one MPS pass.
    """

    sequence: list[int]
    cycle_time: float
    makespan: float
