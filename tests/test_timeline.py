"""Tests for the schedule timeline (the basis of both makespan and the Gantt charts)."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ffll_igls import (  # noqa: E402
    Instance,
    allocate_machines,
    build_timeline,
    ffll,
    simulate_makespan,
)


def _example_b() -> Instance:
    """Report Example B: 3 stages, 5 jobs, jobs 2 & 5 bypass stage 2."""
    return Instance(
        stages=3,
        machines_per_stage=[1, 2, 1],
        n_jobs=5,
        stage_times=np.array(
            [[3, 5, 2, 4, 6], [4, 0, 6, 3, 0], [2, 3, 1, 4, 2]], dtype=float
        ),
    )


def test_timeline_makespan_matches_simulation():
    """The latest finish in the timeline equals the reported makespan."""
    inst = _example_b()
    alloc = allocate_machines(inst)
    sequence = ffll(inst).sequence
    operations = build_timeline(sequence, alloc)
    assert max(op.finish for op in operations) == simulate_makespan(sequence, alloc)


def test_timeline_no_machine_runs_two_jobs_at_once():
    """Operations on the same machine never overlap in time."""
    inst = _example_b()
    alloc = allocate_machines(inst)
    operations = build_timeline(ffll(inst).sequence, alloc)

    by_machine: dict[int, list] = {}
    for op in operations:
        by_machine.setdefault(op.machine, []).append(op)
    for machine_ops in by_machine.values():
        machine_ops.sort(key=lambda o: o.start)
        for earlier, later in zip(machine_ops, machine_ops[1:]):
            assert earlier.finish <= later.start + 1e-9


def test_timeline_durations_equal_processing_times():
    """Each operation lasts exactly its processing time; bypassed stages have none."""
    inst = _example_b()
    alloc = allocate_machines(inst)
    operations = build_timeline(ffll(inst).sequence, alloc)

    for op in operations:
        assert abs((op.finish - op.start) - alloc.p[op.machine, op.job]) < 1e-9
    # Jobs 2 and 5 (0-based 1 and 4) bypass stage 2 -> no op there.
    assert not any(op.stage == 1 and op.job in (1, 4) for op in operations)
