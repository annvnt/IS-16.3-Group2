"""
Regression tests that lock the claims made in the report
(docs/Chapter16_3_Project_Solution.pdf).

These are the guardrail for the "code and report must agree" rule in CLAUDE.md.
If one of these fails, either the code regressed or the report is now wrong — fix
both together, never just loosen the test.
"""

import sys
from pathlib import Path

import numpy as np

# Make src/ importable without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ffll_igls import Instance, ffll, run_experiments  # noqa: E402


def test_example_a_cycle_time_is_18():
    """Report Example A: 2 stages, 4 jobs, no bypass -> optimal cycle time T = 18."""
    inst = Instance(
        stages=2,
        machines_per_stage=[2, 1],
        n_jobs=4,
        stage_times=np.array([[5, 8, 3, 6], [4, 2, 7, 5]], dtype=float),
    )
    _, cycle_time, _ = ffll(inst)
    assert cycle_time == 18.0


def test_example_b_cycle_time_is_20():
    """Report Example B: 3 stages, 5 jobs, jobs 2 & 5 bypass stage 2 -> T = 20."""
    inst = Instance(
        stages=3,
        machines_per_stage=[1, 2, 1],
        n_jobs=5,
        stage_times=np.array(
            [[3, 5, 2, 4, 6], [4, 0, 6, 3, 0], [2, 3, 1, 4, 2]], dtype=float
        ),
    )
    _, cycle_time, _ = ffll(inst)
    assert cycle_time == 20.0


def test_ten_instance_summary_matches_report():
    """Report Section 4.3: IG-LS improves all 10 instances; gap 33.8% -> 15.1%."""
    results = run_experiments()

    assert len(results) == 10

    # Every instance improved (report: "improved every single one of the 10").
    assert all(r["improv"] > 1e-9 for r in results)

    ffll_avg_gap = float(np.mean([r["ffll_gap"] for r in results]))
    igls_avg_gap = float(np.mean([r["igls_gap"] for r in results]))

    # IG-LS is strictly better on average, and the aggregates match the report.
    assert igls_avg_gap < ffll_avg_gap
    assert abs(ffll_avg_gap - 33.8) < 0.5
    assert abs(igls_avg_gap - 15.1) < 0.5
