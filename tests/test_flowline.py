"""Tests for the flow-line geometry and per-job location logic (pure, no matplotlib)."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ffll_igls import Instance, allocate_machines, build_timeline, ffll  # noqa: E402
from ffll_igls.flowline import build_layout, bucket_jobs, group_by_job  # noqa: E402


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


def _ops_by_job(inst: Instance):
    alloc = allocate_machines(inst)
    return group_by_job(build_timeline(ffll(inst).sequence, alloc), inst.n_jobs)


def test_layout_has_one_column_per_stage():
    """build_layout groups machines per stage and gives each stage an x column."""
    layout = build_layout([0, 1, 1, 2])
    assert len(layout.stage_x) == 3
    assert layout.machine_groups == [[0], [1, 2], [3]]
    assert layout.machine_stage == [0, 1, 1, 2]


def test_every_job_lands_in_exactly_one_bucket():
    """At any time, queue + processing + buffer + done accounts for all jobs."""
    inst = _example_b()
    ops_by_job = _ops_by_job(inst)
    for t in (0.0, 5.0, 12.0, 1000.0):
        b = bucket_jobs(ops_by_job, t)
        counted = (
            len(b.processing) + len(b.waiting) + len(b.done)
            + sum(len(jobs) for jobs in b.buffer.values())
        )
        assert counted == inst.n_jobs


def test_nothing_done_at_start_all_done_after_makespan():
    """The board is empty of completed jobs at t=0 and full of them past the makespan."""
    inst = _example_b()
    ops_by_job = _ops_by_job(inst)
    makespan = ffll(inst).makespan

    assert bucket_jobs(ops_by_job, 0.0).done == []
    finished = bucket_jobs(ops_by_job, makespan + 1.0)
    assert len(finished.done) == inst.n_jobs
    assert finished.processing == [] and finished.buffer == {}
