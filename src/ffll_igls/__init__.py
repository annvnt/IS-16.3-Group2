"""FFLL vs IG-LS scheduler for a Flexible Flow Line with bypass and limited buffers.

Pinedo Chapter 16.3 — problem ``FFs | bypass, b_i < inf | C_max``.

Public API:
    - :class:`Instance`, :class:`Allocation`, :class:`Schedule` — data structures.
    - :func:`ffll` — the three-phase FFLL heuristic.
    - :func:`igls` / :class:`IGLSConfig` — Iterated Greedy with Local Search.
    - :func:`generate_instance` / :class:`InstanceConfig`, :func:`lower_bound`.
    - :func:`run_experiments` — the 10-instance comparison harness.

Run the experiment suite with ``python -m ffll_igls``.
"""

from __future__ import annotations

from .allocation import allocate_machines
from .experiments import InstanceResult, Scenario, run_experiments
from .ffll import ffll
from .igls import IGLSConfig, igls, igls_states, local_search_2opt, perturb
from .instances import InstanceConfig, generate_instance, lower_bound
from .models import Allocation, Instance, Schedule
from .reporting import print_experiment_report, trace_instance
from .sequencing import dynamic_balancing, overload_score
from .simulation import bottleneck_cycle_time, simulate_makespan
from .timeline import Operation, build_timeline

__all__ = [
    "Instance",
    "Allocation",
    "Schedule",
    "allocate_machines",
    "dynamic_balancing",
    "overload_score",
    "bottleneck_cycle_time",
    "simulate_makespan",
    "ffll",
    "igls",
    "igls_states",
    "IGLSConfig",
    "local_search_2opt",
    "perturb",
    "Operation",
    "build_timeline",
    "generate_instance",
    "InstanceConfig",
    "lower_bound",
    "Scenario",
    "InstanceResult",
    "run_experiments",
    "print_experiment_report",
    "trace_instance",
]
