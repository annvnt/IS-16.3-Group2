"""Entry point: reproduce the report's experiments. Run with ``python -m ffll_igls``."""

from __future__ import annotations

from .experiments import run_experiments
from .instances import InstanceConfig, generate_instance
from .reporting import print_experiment_report, trace_instance


def main() -> None:
    """Run the 10-instance comparison plus two detailed traces (report Section 4)."""
    print("\n" + "=" * 70)
    print(" PART 4: FFLL vs IG-LS on 10 Random Instances")
    print("=" * 70 + "\n")

    print_experiment_report(run_experiments())

    trace_instance(
        generate_instance(InstanceConfig(5, 2, 2, 10, 0.10, seed=20)),
        "Instance 2 — Small, light bypass",
    )
    trace_instance(
        generate_instance(InstanceConfig(10, 4, 2, 10, 0.15, seed=70)),
        "Instance 7 — Large, 4-stage",
    )

    print("\nDone.")


if __name__ == "__main__":
    main()
