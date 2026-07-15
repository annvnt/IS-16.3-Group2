"""Geometry and per-job location logic for the animated flow line (no matplotlib).

Given a schedule timeline, this answers "where is each job at time t?" — processing
in a machine, waiting in a buffer, still queued, or done — and lays out the stage/machine
coordinates. The drawing lives in :mod:`ffll_igls.animation`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .timeline import Operation

_EPS = 1e-9
TOKEN_SPACING = 0.52  # vertical gap between stacked job tokens

# Job location categories at a given time.
WAITING = "waiting"        # released order not yet reached — still in the input queue
PROCESSING = "processing"  # currently on a machine
BUFFER = "buffer"          # finished a stage, waiting for the next (work-in-process)
DONE = "done"              # left the system


@dataclass(frozen=True)
class Layout:
    """Fixed screen coordinates for one flow line."""

    stage_x: list[float]            # x center of each stage column
    machine_y: dict[int, float]     # y of each global machine
    machine_stage: list[int]        # stage of each global machine
    machine_groups: list[list[int]]  # machine indices per stage
    buffer_x: list[float]           # x of the buffer after each stage
    input_x: float
    output_x: float


@dataclass
class Buckets:
    """Jobs grouped by where they are at one instant."""

    processing: list[tuple[int, int, float]] = field(default_factory=list)  # (job, machine, progress)
    waiting: list[int] = field(default_factory=list)
    done: list[int] = field(default_factory=list)
    buffer: dict[int, list[int]] = field(default_factory=dict)  # stage -> jobs


def build_layout(machine_stage: list[int]) -> Layout:
    """Place stages as columns left->right and machines as vertical slots per stage."""
    n_stages = max(machine_stage) + 1
    groups: list[list[int]] = [[] for _ in range(n_stages)]
    for machine, stage in enumerate(machine_stage):
        groups[stage].append(machine)

    stage_x = [1.5 + stage * 2.5 for stage in range(n_stages)]
    machine_y = {
        machine: (len(group) - 1) / 2 - local
        for group in groups
        for local, machine in enumerate(group)
    }
    return Layout(
        stage_x=stage_x,
        machine_y=machine_y,
        machine_stage=list(machine_stage),
        machine_groups=groups,
        buffer_x=[x + 1.25 for x in stage_x],
        input_x=-0.6,
        output_x=stage_x[-1] + 1.75,
    )


def group_by_job(operations: list[Operation], n_jobs: int) -> list[list[Operation]]:
    """Bucket operations by job, each list ordered by stage."""
    by_job: list[list[Operation]] = [[] for _ in range(n_jobs)]
    for op in operations:
        by_job[op.job].append(op)
    for ops in by_job:
        ops.sort(key=lambda o: o.stage)
    return by_job


def classify(ops: list[Operation], t: float) -> tuple[str, int, float]:
    """Locate one job at time ``t``.

    Returns ``(status, key, progress)`` where ``key`` is the machine index when
    processing, the just-finished stage index when buffered, else -1; and
    ``progress`` is the 0..1 fraction done when processing, else 0.
    """
    if not ops or t < ops[0].start - _EPS:
        return WAITING, -1, 0.0
    if t >= ops[-1].finish - _EPS:
        return DONE, -1, 0.0
    for op in ops:
        if op.start - _EPS <= t < op.finish - _EPS:
            return PROCESSING, op.machine, (t - op.start) / (op.finish - op.start)
    for done_op, next_op in zip(ops, ops[1:]):
        if done_op.finish - _EPS <= t < next_op.start - _EPS:
            return BUFFER, done_op.stage, 0.0
    return BUFFER, ops[-1].stage, 0.0  # safety net (should not be reached)


def bucket_jobs(ops_by_job: list[list[Operation]], t: float) -> Buckets:
    """Group every job into queue / processing / buffer / done at time ``t``."""
    buckets = Buckets()
    for job, ops in enumerate(ops_by_job):
        status, key, progress = classify(ops, t)
        if status == PROCESSING:
            buckets.processing.append((job, key, progress))
        elif status == WAITING:
            buckets.waiting.append(job)
        elif status == DONE:
            buckets.done.append(job)
        else:
            buckets.buffer.setdefault(key, []).append(job)
    return buckets


def vertical_extent(layout: Layout, n_jobs: int) -> float:
    """Half-height needed to fit the tallest stage and the longest token stack."""
    machine_half = max((abs(y) for y in layout.machine_y.values()), default=0.0) + 1.0
    stack_half = (n_jobs - 1) / 2 * TOKEN_SPACING + 0.8
    return max(2.2, machine_half, stack_half)
