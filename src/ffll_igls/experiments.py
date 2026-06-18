"""Experiment harness: run FFLL vs IG-LS over a fixed suite of instances.

Computation only — printing lives in :mod:`ffll_igls.reporting`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from .ffll import ffll
from .igls import IGLSConfig, igls
from .instances import InstanceConfig, generate_instance, lower_bound


@dataclass(frozen=True)
class Scenario:
    """A named instance configuration for the experiment suite."""

    config: InstanceConfig
    label: str


@dataclass(frozen=True)
class InstanceResult:
    """Measured outcome of running both algorithms on one instance."""

    index: int
    label: str
    n_jobs: int
    n_stages: int
    lower_bound: float
    ffll_makespan: float
    ffll_seconds: float
    igls_makespan: float
    igls_seconds: float

    @property
    def ffll_gap(self) -> float:
        """Percentage gap of the FFLL makespan above the lower bound."""
        return _percentage_gap(self.ffll_makespan, self.lower_bound)

    @property
    def igls_gap(self) -> float:
        """Percentage gap of the IG-LS makespan above the lower bound."""
        return _percentage_gap(self.igls_makespan, self.lower_bound)

    @property
    def improvement(self) -> float:
        """Percentage makespan reduction of IG-LS relative to FFLL."""
        if self.ffll_makespan <= 0:
            return 0.0
        return 100.0 * (self.ffll_makespan - self.igls_makespan) / self.ffll_makespan


# Ten instances with deliberately varied size, stages, machines, and bypass rate.
SCENARIOS: list[Scenario] = [
    Scenario(InstanceConfig(4, 2, 2, 8, 0.00, 10), "Small, no bypass"),
    Scenario(InstanceConfig(5, 2, 2, 10, 0.10, 20), "Small, light bypass"),
    Scenario(InstanceConfig(6, 3, 2, 8, 0.15, 30), "Medium, 3-stage"),
    Scenario(InstanceConfig(7, 3, 2, 12, 0.20, 40), "Medium, higher bypass"),
    Scenario(InstanceConfig(8, 4, 2, 10, 0.15, 50), "Medium-large, 4-stage"),
    Scenario(InstanceConfig(8, 3, 3, 10, 0.10, 60), "Medium, 3 mach/stage"),
    Scenario(InstanceConfig(10, 4, 2, 10, 0.15, 70), "Large, 4-stage"),
    Scenario(InstanceConfig(10, 5, 2, 8, 0.20, 80), "Large, 5-stage"),
    Scenario(InstanceConfig(12, 4, 2, 12, 0.15, 90), "XL, 4-stage"),
    Scenario(InstanceConfig(12, 5, 2, 10, 0.25, 100), "XL, 5-stage, high bypass"),
]


def run_experiments() -> list[InstanceResult]:
    """Evaluate FFLL and IG-LS on every scenario in :data:`SCENARIOS`.

    Returns:
        One :class:`InstanceResult` per scenario, in suite order.
    """
    return [_evaluate(index, scenario) for index, scenario in enumerate(SCENARIOS, 1)]


def _evaluate(index: int, scenario: Scenario) -> InstanceResult:
    """Generate one instance and time both algorithms on it."""
    inst = generate_instance(scenario.config)
    ffll_schedule, ffll_seconds = _timed(lambda: ffll(inst))
    igls_schedule, igls_seconds = _timed(
        lambda: igls(inst, IGLSConfig(seed=scenario.config.seed))
    )
    return InstanceResult(
        index=index,
        label=scenario.label,
        n_jobs=inst.n_jobs,
        n_stages=inst.stages,
        lower_bound=lower_bound(inst),
        ffll_makespan=ffll_schedule.makespan,
        ffll_seconds=ffll_seconds,
        igls_makespan=igls_schedule.makespan,
        igls_seconds=igls_seconds,
    )


def _timed(action: Callable[[], object]) -> tuple[object, float]:
    """Run ``action`` and return its result alongside the elapsed wall-clock seconds."""
    start = time.perf_counter()
    result = action()
    return result, time.perf_counter() - start


def _percentage_gap(value: float, baseline: float) -> float:
    """Return ``value`` as a percentage above ``baseline`` (0 if baseline <= 0)."""
    if baseline <= 0:
        return 0.0
    return 100.0 * (value - baseline) / baseline
