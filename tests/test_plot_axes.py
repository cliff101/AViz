"""Axis scaling helpers."""

from aviz.ui.plot_axes import scaled_linear_range, scaled_log_range


def test_scaled_linear_zoom_in():
    lo, hi = scaled_linear_range(0, 100, scale=2.0)
    assert hi - lo == 50


def test_scaled_log_range():
    lo, hi = scaled_log_range(20, 12000, scale=1.0)
    assert lo < hi
