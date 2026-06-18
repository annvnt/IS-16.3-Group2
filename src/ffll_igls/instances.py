"""Random instance generation and the bottleneck lower bound."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .allocation import allocate_machines
from .models import Instance


@dataclass(frozen=True)
class InstanceConfig:
    """Parameters for generating a random flexible-flow-line instance.

    Attributes:
        n_jobs: Number of jobs in the MPS.
        n_stages: Number of stages.
        max_machines_per_stage: Each stage gets 1..this many machines (random).
        max_proc_time: Processing times are drawn uniformly from ``[1, this]``.
        bypass_prob: Probability that a job bypasses a given stage.
        seed: Seed for reproducible generation.
    """

    n_jobs: int
    n_stages: int
    max_machines_per_stage: int = 2
    max_proc_time: int = 10
    bypass_prob: float = 0.15
    seed: int = 0


def generate_instance(config: InstanceConfig) -> Instance:
    """Generate a random instance according to ``config``.

    Args:
        config: Generation parameters.

    Returns:
        A randomly generated :class:`Instance` (every job has >= 1 active stage).
    """
    rng = np.random.default_rng(config.seed)
    machines_per_stage = [
        int(rng.integers(1, config.max_machines_per_stage + 1))
        for _ in range(config.n_stages)
    ]
    return Instance(
        stages=config.n_stages,
        machines_per_stage=machines_per_stage,
        n_jobs=config.n_jobs,
        stage_times=_random_stage_times(rng, config),
    )


def lower_bound(inst: Instance) -> float:
    """Return the bottleneck-workload lower bound on cycle time (after LPT)."""
    return float(allocate_machines(inst).W.max())


def _random_stage_times(rng: np.random.Generator, config: InstanceConfig) -> np.ndarray:
    """Draw the ``(stages, jobs)`` processing matrix; guarantee no all-bypass job."""
    times = np.zeros((config.n_stages, config.n_jobs))
    for stage in range(config.n_stages):
        for job in range(config.n_jobs):
            if rng.random() >= config.bypass_prob:
                times[stage, job] = float(rng.integers(1, config.max_proc_time + 1))
    _ensure_every_job_processed(rng, times, config)
    return times


def _ensure_every_job_processed(
    rng: np.random.Generator, times: np.ndarray, config: InstanceConfig
) -> None:
    """Give any fully-bypassed job one random active stage. Mutates ``times``."""
    for job in range(config.n_jobs):
        if times[:, job].sum() == 0:
            stage = int(rng.integers(0, config.n_stages))
            times[stage, job] = float(rng.integers(1, config.max_proc_time + 1))
