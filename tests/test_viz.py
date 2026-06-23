"""Smoke test for the visualization module (skipped if matplotlib is absent)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

pytest.importorskip("matplotlib")

from ffll_igls import InstanceConfig, generate_instance  # noqa: E402
from ffll_igls.viz import render_overview  # noqa: E402


def test_render_overview_writes_a_png(tmp_path):
    """render_overview produces a non-empty PNG for a small instance."""
    inst = generate_instance(InstanceConfig(6, 3, 2, 8, 0.15, 30))
    out = render_overview(inst, tmp_path / "fig.png", label="test instance")
    assert out.exists()
    assert out.stat().st_size > 0
