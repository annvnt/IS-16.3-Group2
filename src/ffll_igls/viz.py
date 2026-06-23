"""Visualize FFLL vs IG-LS: stage-by-stage Gantt charts plus the IG-LS convergence.

Run as a script to render a figure::

    PYTHONPATH=src python -m ffll_igls.viz --instance 5 --out figures/algorithm_overview.png

The figure has three panels for one instance: the FFLL schedule, the IG-LS
schedule (so the makespan shrink is visible), and the IG-LS convergence curve.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # file output only, no interactive display
import matplotlib.pyplot as plt  # noqa: E402

from .allocation import allocate_machines  # noqa: E402
from .experiments import SCENARIOS  # noqa: E402
from .ffll import ffll  # noqa: E402
from .igls import IGLSConfig, igls, igls_states  # noqa: E402
from .instances import generate_instance  # noqa: E402
from .models import Allocation, Instance, Schedule  # noqa: E402
from .timeline import build_timeline  # noqa: E402

_BOTTLENECK_COLOR = "#c0392b"
_FFLL_COLOR = "#e67e22"
_IGLS_COLOR = "#2980b9"
_LB_COLOR = "#7f8c8d"


def render_overview(
    inst: Instance, out_path: Path, label: str = "", config: IGLSConfig | None = None
) -> Path:
    """Render the FFLL/IG-LS Gantt + convergence figure for one instance.

    Args:
        inst: The scheduling instance to visualize.
        out_path: Destination PNG path (parent directories are created).
        label: Human-readable instance label for the figure title.
        config: IG-LS tuning parameters; defaults to :class:`IGLSConfig`.

    Returns:
        The path the figure was written to.
    """
    config = config or IGLSConfig()
    alloc = allocate_machines(inst)
    ffll_schedule = ffll(inst)
    igls_schedule = igls(inst, config)
    history = [makespan for _, makespan in igls_states(alloc, config)]
    lower_bound = float(alloc.W.max())

    fig, (ax_ffll, ax_igls, ax_conv) = plt.subplots(
        3, 1, figsize=(12, 12), height_ratios=[3, 3, 2]
    )
    _plot_gantt(ax_ffll, inst, alloc, ffll_schedule, "FFLL", lower_bound)
    _plot_gantt(ax_igls, inst, alloc, igls_schedule, "IG-LS", lower_bound)
    _plot_convergence(ax_conv, history, ffll_schedule.makespan, lower_bound)

    title = label or f"{inst.n_jobs} jobs, {inst.stages} stages"
    fig.suptitle(
        f"FFLL vs IG-LS  —  {title}\n"
        f"makespan {ffll_schedule.makespan:.0f} -> {igls_schedule.makespan:.0f}  "
        f"(lower bound {lower_bound:.0f})",
        fontsize=14,
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def _plot_gantt(
    ax: plt.Axes,
    inst: Instance,
    alloc: Allocation,
    schedule: Schedule,
    name: str,
    lower_bound: float,
) -> None:
    """Draw one schedule as a Gantt chart (machine rows x time), colored by job.

    Machines are indexed stage by stage, so the global machine index doubles as
    the Gantt row (stage 1 machines on top).
    """
    colors = plt.colormaps["tab20"]

    for op in build_timeline(schedule.sequence, alloc):
        ax.barh(
            op.machine, op.finish - op.start, left=op.start, height=0.7,
            color=colors(op.job % 20), edgecolor="white", linewidth=0.7,
        )
        ax.text(
            (op.start + op.finish) / 2, op.machine, str(op.job + 1),
            ha="center", va="center", fontsize=8, fontweight="bold", color="black",
        )

    bottleneck = int(alloc.W.argmax())
    ax.axvline(lower_bound, color=_LB_COLOR, linestyle=":", linewidth=1.5)
    ax.axvline(schedule.makespan, color=_BOTTLENECK_COLOR, linestyle="--", linewidth=1.5)

    ax.set_yticks(range(len(alloc.machine_stage)))
    ax.set_yticklabels(_machine_labels(alloc.machine_stage, bottleneck))
    ax.invert_yaxis()
    ax.set_xlabel("time")
    ax.set_xlim(0, schedule.makespan * 1.12)
    gap = 100 * (schedule.makespan - lower_bound) / lower_bound if lower_bound else 0
    ax.set_title(
        f"{name} schedule — makespan {schedule.makespan:.0f} "
        f"(+{gap:.0f}% over lower bound)",
        fontsize=11, loc="left",
    )
    ax.text(
        schedule.makespan, -0.6, f" makespan {schedule.makespan:.0f}",
        color=_BOTTLENECK_COLOR, fontsize=8, va="bottom",
    )


def _plot_convergence(
    ax: plt.Axes, history: list[float], ffll_makespan: float, lower_bound: float
) -> None:
    """Plot the IG-LS incumbent makespan per iteration against FFLL and the bound."""
    ax.step(range(len(history)), history, where="post", color=_IGLS_COLOR,
            linewidth=2, label="IG-LS incumbent")
    ax.axhline(ffll_makespan, color=_FFLL_COLOR, linestyle="--", linewidth=1.5,
               label=f"FFLL ({ffll_makespan:.0f})")
    ax.axhline(lower_bound, color=_LB_COLOR, linestyle=":", linewidth=1.5,
               label=f"lower bound ({lower_bound:.0f})")
    ax.set_xlabel("IG-LS iteration")
    ax.set_ylabel("best makespan")
    ax.set_xlim(0, max(1, len(history) - 1))
    ax.set_title("IG-LS convergence", fontsize=11, loc="left")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)


def _machine_labels(machine_stage: list[int], bottleneck: int) -> list[str]:
    """Build ``S{stage}.M{n}`` row labels, flagging the bottleneck machine."""
    seen_in_stage: dict[int, int] = {}
    labels = []
    for machine, stage in enumerate(machine_stage):
        seen_in_stage[stage] = seen_in_stage.get(stage, 0) + 1
        flag = "  (bottleneck)" if machine == bottleneck else ""
        labels.append(f"S{stage + 1}.M{seen_in_stage[stage]}{flag}")
    return labels


def main() -> None:
    """CLI entry point: render the overview figure for one named instance."""
    parser = argparse.ArgumentParser(description="Render the FFLL vs IG-LS figure.")
    parser.add_argument("--instance", type=int, default=7,
                        help="scenario number 1..10 (default: 7)")
    parser.add_argument("--out", type=Path, default=Path("figures/algorithm_overview.png"),
                        help="output PNG path")
    args = parser.parse_args()

    scenario = SCENARIOS[args.instance - 1]
    inst = generate_instance(scenario.config)
    path = render_overview(
        inst, args.out, label=f"Instance {args.instance} — {scenario.label}"
    )
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
