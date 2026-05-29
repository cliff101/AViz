"""Frequency axis tick helpers."""

from aviz.analysis.freq_scales import focus_tick_pairs
from aviz.ui.freq_axis import axis_label_for_scale


def test_focus_ticks_in_unit_interval():
    ticks = focus_tick_pairs(20, 12_000, n=6)
    xs = [t[0] for t in ticks]
    assert xs[0] == 0.0
    assert xs[-1] == 1.0
    assert all(0 <= x <= 1 for x in xs)


def test_focus_axis_label():
    assert "expanded" in axis_label_for_scale("focus").lower()
