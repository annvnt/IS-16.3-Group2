"""Smoke test for the race animation (skipped if matplotlib / ffmpeg are absent)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

pytest.importorskip("matplotlib")
from matplotlib.animation import FFMpegWriter  # noqa: E402

from ffll_igls import InstanceConfig, generate_instance  # noqa: E402
from ffll_igls.animation import render_race  # noqa: E402


def test_render_race_writes_mp4_and_gif(tmp_path):
    """render_race produces non-empty MP4 + GIF (tiny frame count for speed)."""
    if not FFMpegWriter.isAvailable():
        pytest.skip("ffmpeg not available")
    inst = generate_instance(InstanceConfig(6, 3, 2, 8, 0.15, 30))
    paths = render_race(inst, tmp_path / "race", label="test", fps=2, frames=3)
    assert [p.suffix for p in paths] == [".mp4", ".gif"]
    assert all(p.exists() and p.stat().st_size > 0 for p in paths)
