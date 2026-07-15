"""Animated FFLL-vs-IG-LS race: two flow lines run the same jobs side by side.

Jobs flow left->right through stage columns (queue -> machine -> buffer -> done) while a
live panel on the right tracks the clock, WIP, busy machines, and completion. Watch the
IG-LS line clear the board while FFLL is still working.

Render with::

    PYTHONPATH=src python -m ffll_igls.animation --instance 6 --out figures/race
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # file output only
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402

from .allocation import allocate_machines  # noqa: E402
from .experiments import SCENARIOS  # noqa: E402
from .ffll import ffll  # noqa: E402
from .flowline import (  # noqa: E402
    TOKEN_SPACING,
    Layout,
    bucket_jobs,
    build_layout,
    group_by_job,
    vertical_extent,
)
from .igls import IGLSConfig, igls  # noqa: E402
from .instances import generate_instance  # noqa: E402
from .timeline import Operation, build_timeline  # noqa: E402

_FFLL_COLOR = "#e67e22"
_IGLS_COLOR = "#2980b9"
_BOTTLENECK_COLOR = "#c0392b"
_EPS = 1e-9


@dataclass(frozen=True)
class LineView:
    """One side of the race: a named schedule plus its precomputed operations."""

    name: str
    color: str
    ops_by_job: list[list[Operation]]
    makespan: float
    bottleneck: int


def render_race(
    inst, out_stem: Path, label: str = "", config: IGLSConfig | None = None,
    fps: int = 20, frames: int = 150,
) -> list[Path]:
    """Render the FFLL-vs-IG-LS flow-line race to an MP4 and a GIF.

    Args:
        inst: The instance to animate.
        out_stem: Output path without suffix (``.mp4``/``.gif`` are appended).
        label: Instance label for the figure title.
        config: IG-LS tuning parameters; defaults to :class:`IGLSConfig`.
        fps: Frames per second.
        frames: Number of time samples across the race.

    Returns:
        The paths written (``.mp4`` then ``.gif``).
    """
    config = config or IGLSConfig()
    alloc = allocate_machines(inst)
    layout = build_layout(alloc.machine_stage)
    bottleneck = int(alloc.W.argmax())
    n_machines = len(alloc.machine_stage)

    ffll_schedule, igls_schedule = ffll(inst), igls(inst, config)
    views = [
        LineView("FFLL", _FFLL_COLOR,
                 group_by_job(build_timeline(ffll_schedule.sequence, alloc), inst.n_jobs),
                 ffll_schedule.makespan, bottleneck),
        LineView("IG-LS", _IGLS_COLOR,
                 group_by_job(build_timeline(igls_schedule.sequence, alloc), inst.n_jobs),
                 igls_schedule.makespan, bottleneck),
    ]
    horizon = max(view.makespan for view in views)
    times = list(np.linspace(0, horizon, frames)) + [horizon] * fps  # hold the final frame

    fig = plt.figure(figsize=(13, 7.8))
    grid = fig.add_gridspec(3, 2, width_ratios=[3.2, 1], height_ratios=[1, 1, 0.55],
                            wspace=0.04, hspace=0.32)
    ax_top, ax_bottom = fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[1, 0])
    ax_data = fig.add_subplot(grid[0:2, 1])
    ax_table = fig.add_subplot(grid[2, :])
    fig.suptitle(f"FFLL vs IG-LS race  —  {label}", fontsize=14, fontweight="bold", y=0.99)
    fig.text(0.5, 0.945, r"Graham: $FF_s \mid bypass,\; b_i < \infty \mid C_{\max}$",
             ha="center", fontsize=11, color="#444")
    _draw_input_table(ax_table, inst)  # static — drawn once, untouched by update()
    half = vertical_extent(layout, inst.n_jobs)

    def update(index: int) -> None:
        t = times[index]
        _draw_flowline(ax_top, layout, views[0], t, half)
        _draw_flowline(ax_bottom, layout, views[1], t, half)
        _draw_panel(ax_data, t, views, n_machines)

    anim = FuncAnimation(fig, update, frames=len(times), interval=1000 / fps)
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    mp4, gif = out_stem.with_suffix(".mp4"), out_stem.with_suffix(".gif")
    anim.save(str(mp4), writer=FFMpegWriter(fps=fps), dpi=120)
    anim.save(str(gif), writer=PillowWriter(fps=fps), dpi=90)
    plt.close(fig)
    return [mp4, gif]


def _draw_flowline(ax, layout: Layout, view: LineView, t: float, half: float) -> None:
    """Draw one flow line at time ``t``: stage columns, machines, and job tokens."""
    ax.clear()
    ax.set_xlim(layout.input_x - 0.7, layout.output_x + 0.9)
    ax.set_ylim(-half, half)
    ax.axis("off")
    ax.set_title(view.name, loc="left", fontsize=12, fontweight="bold", color=view.color)
    colors = plt.colormaps["tab20"]

    ax.text(layout.input_x, half - 0.4, "queue", ha="center", fontsize=9, color="#555")
    ax.text(layout.output_x, half - 0.4, "done", ha="center", fontsize=9, color="#555")
    for stage, machines in enumerate(layout.machine_groups):
        x = layout.stage_x[stage]
        ax.text(x, half - 0.4, f"Stage {stage + 1}", ha="center", fontsize=9, color="#555")
        if stage + 1 < len(layout.machine_groups):
            ax.annotate("", xy=(layout.stage_x[stage + 1] - 0.6, 0), xytext=(x + 0.6, 0),
                        arrowprops=dict(arrowstyle="->", color="#dcdcdc", lw=1.5))
        for machine in machines:
            on_bottleneck = machine == view.bottleneck
            ax.add_patch(FancyBboxPatch(
                (x - 0.5, layout.machine_y[machine] - 0.4), 1.0, 0.8,
                boxstyle="round,pad=0.02", facecolor="#f7f7f7",
                edgecolor=_BOTTLENECK_COLOR if on_bottleneck else "#999",
                linewidth=2.0 if on_bottleneck else 1.0, zorder=1))

    buckets = bucket_jobs(view.ops_by_job, t)
    for job, machine, progress in buckets.processing:
        _draw_token(ax, layout.stage_x[layout.machine_stage[machine]],
                    layout.machine_y[machine], job, colors(job % 20), progress)
    _stack(ax, layout.input_x, buckets.waiting, colors)
    _stack(ax, layout.output_x, buckets.done, colors)
    for stage, jobs in buckets.buffer.items():
        _stack(ax, layout.buffer_x[stage], jobs, colors)


def _draw_panel(ax, t: float, views: list[LineView], n_machines: int) -> None:
    """Draw the live data panel: clock, per-line WIP / busy / done and progress bars."""
    ax.clear()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.5, 0.96, f"t = {t:0.1f}", ha="center", fontsize=20, fontweight="bold")

    block_top = 0.78
    finished_flags = []
    for view in views:
        buckets = bucket_jobs(view.ops_by_job, t)
        wip = len(buckets.processing) + sum(len(j) for j in buckets.buffer.values())
        total = len(view.ops_by_job)
        finished = t >= view.makespan - _EPS
        finished_flags.append(finished)

        ax.text(0.05, block_top, view.name, fontsize=13, fontweight="bold", color=view.color)
        ax.text(0.05, block_top - 0.07, f"WIP {wip}    busy {len(buckets.processing)}/{n_machines}",
                fontsize=10, color="#333")
        ax.text(0.05, block_top - 0.13, f"done {len(buckets.done)}/{total}",
                fontsize=10, color="#333")
        fraction = len(buckets.done) / total if total else 0.0
        ax.add_patch(Rectangle((0.05, block_top - 0.21), 0.9, 0.04,
                               facecolor="#eee", edgecolor="#ccc"))
        ax.add_patch(Rectangle((0.05, block_top - 0.21), 0.9 * fraction, 0.04, facecolor=view.color))
        marker = f"DONE at {view.makespan:.0f}" if finished else "running..."
        ax.text(0.95, block_top - 0.28, marker, ha="right", fontsize=10,
                color=view.color if finished else "#999",
                fontweight="bold" if finished else "normal")
        block_top -= 0.4

    if finished_flags == [False, True]:
        ax.text(0.5, 0.03, "IG-LS finished —\nFFLL still running", ha="center",
                fontsize=11, color=_IGLS_COLOR, fontweight="bold")


def _draw_token(ax, x: float, y: float, job: int, color, progress: float | None) -> None:
    """Draw one job token (circle + number), with a progress bar when processing."""
    ax.add_patch(Circle((x, y), 0.32, facecolor=color, edgecolor="black", linewidth=0.8, zorder=3))
    ax.text(x, y, str(job + 1), ha="center", va="center", fontsize=8.5, fontweight="bold", zorder=4)
    if progress is not None:
        ax.add_patch(Rectangle((x - 0.32, y - 0.52), 0.64, 0.1, facecolor="#ddd", zorder=3))
        ax.add_patch(Rectangle((x - 0.32, y - 0.52), 0.64 * progress, 0.1, facecolor="#2ecc71", zorder=4))


def _stack(ax, x: float, jobs: list[int], colors) -> None:
    """Draw a vertical stack of job tokens centered on y=0 (queue, buffer, done)."""
    for i, job in enumerate(jobs):
        y = ((len(jobs) - 1) / 2 - i) * TOKEN_SPACING
        _draw_token(ax, x, y, job, colors(job % 20), None)


def _draw_input_table(ax, inst) -> None:
    """Draw the static processing-time table p[stage, job] (· = bypass), once per figure."""
    ax.axis("off")
    ax.set_title("Processing times  p[stage, job]   ( · = bypass )", fontsize=10, pad=4)
    colors = plt.colormaps["tab20"]
    cell_text = [
        ["·" if inst.stage_times[s, j] == 0 else f"{int(inst.stage_times[s, j])}"
         for j in range(inst.n_jobs)]
        for s in range(inst.stages)
    ]
    table = ax.table(
        cellText=cell_text,
        rowLabels=[f"Stage {s + 1}" for s in range(inst.stages)],
        colLabels=[f"Job {j + 1}" for j in range(inst.n_jobs)],
        loc="center", cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.35)
    for j in range(inst.n_jobs):
        header = table[0, j]
        header.set_facecolor(colors(j % 20))
        header.set_text_props(color="white", fontweight="bold")
        for s in range(inst.stages):
            if inst.stage_times[s, j] == 0:
                table[s + 1, j].set_facecolor("#f0f0f0")
                table[s + 1, j].get_text().set_color("#bbbbbb")


def main() -> None:
    """CLI entry point: render the race for one named scenario."""
    parser = argparse.ArgumentParser(description="Render the FFLL vs IG-LS flow-line race.")
    parser.add_argument("--instance", type=int, default=6,
                        help="scenario number 1..10 (default: 6)")
    parser.add_argument("--out", type=Path, default=Path("figures/race"),
                        help="output path stem (.mp4/.gif appended)")
    args = parser.parse_args()

    scenario = SCENARIOS[args.instance - 1]
    inst = generate_instance(scenario.config)
    paths = render_race(inst, args.out, label=f"Instance {args.instance} — {scenario.label}")
    print("wrote " + ", ".join(str(p) for p in paths))


if __name__ == "__main__":
    main()
