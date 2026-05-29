"""Waterfall history buffer."""

from __future__ import annotations

import numpy as np
import pytest

from aviz.ui.widgets.waterfall_plot import WaterfallPlotWidget


@pytest.fixture
def wf(qtbot):
    w = WaterfallPlotWidget()
    qtbot.addWidget(w)
    w.configure(
        colormap="inferno",
        db_min=-50,
        db_max=70,
        gamma=1.0,
        depth=32,
        freq_scale="linear",
        f_min_hz=20,
        f_max_hz=1000,
        scale_x=1.0,
    )
    return w


def test_push_frame_fills_buffer(wf: WaterfallPlotWidget) -> None:
    freqs = np.linspace(20, 1000, 64)
    db = np.linspace(-70, -30, 64)
    for _ in range(40):
        wf.push_frame(freqs, db)
    assert wf._buffer is not None
    assert wf._buffer.shape == (32, 64)
    assert wf._buffer[-1, 0] > 0


def test_configure_resets_on_depth_change(wf: WaterfallPlotWidget) -> None:
    freqs = np.linspace(20, 1000, 8)
    wf.push_frame(freqs, np.full(8, -40.0))
    wf.configure(
        colormap="inferno",
        db_min=-50,
        db_max=70,
        gamma=1.0,
        depth=64,
        freq_scale="linear",
        f_min_hz=20,
        f_max_hz=1000,
        scale_x=1.0,
        reset_buffer=True,
    )
    assert wf._buffer is None
