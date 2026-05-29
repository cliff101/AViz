"""Helpers for independent horizontal / vertical axis scaling."""

from __future__ import annotations

import math
from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent

WheelZoomAxis = Literal["x", "y", "both"]

# Horizontal thirds: left / center / right → y / both / x
_WHEEL_ZONE_EDGE = 1.0 / 3.0


def wheel_zoom_axis(ev: QWheelEvent, width: int, height: int) -> WheelZoomAxis:
    """Pick wheel zoom target from cursor X within the plot.

    Left third → vertical axis only (level / frequency on spectrogram).
    Center third → both axes.
    Right third → horizontal axis only (frequency / time).
    """
    x = ev.position().x() / max(width, 1)
    if x < _WHEEL_ZONE_EDGE:
        return "y"
    if x > 1.0 - _WHEEL_ZONE_EDGE:
        return "x"
    return "both"


def apply_wheel_zoom(
    viewbox,
    ev: QWheelEvent,
    width: int,
    height: int,
    *,
    axis_pick: bool,
) -> bool:
    """Apply wheel zoom to a pyqtgraph ViewBox. Returns True if handled."""
    delta = ev.angleDelta().y()
    if delta == 0:
        return False
    factor = 0.9 if delta > 0 else 1.1
    mods = ev.modifiers()
    if mods & Qt.KeyboardModifier.ShiftModifier:
        viewbox.scaleBy((factor, 1))
    elif mods & Qt.KeyboardModifier.ControlModifier:
        viewbox.scaleBy((1, factor))
    elif axis_pick:
        axis = wheel_zoom_axis(ev, width, height)
        if axis == "x":
            viewbox.scaleBy((factor, 1))
        elif axis == "y":
            viewbox.scaleBy((1, factor))
        else:
            viewbox.scaleBy((factor, factor))
    else:
        viewbox.scaleBy((factor, factor))
    return True


def scaled_linear_range(
    low: float,
    high: float,
    scale: float,
) -> tuple[float, float]:
    """Zoom around center; scale > 1 = zoom in (narrower range)."""
    scale = max(scale, 0.05)
    center = (low + high) / 2.0
    half = (high - low) / 2.0 / scale
    return center - half, center + half


def scaled_log_range(
    f_min_hz: float,
    f_max_hz: float,
    scale: float,
) -> tuple[float, float]:
    """Log-frequency axis limits for pyqtgraph log X mode."""
    scale = max(scale, 0.05)
    lo = math.log10(max(f_min_hz, 1.0))
    hi = math.log10(max(f_max_hz, f_min_hz + 1.0))
    center = (lo + hi) / 2.0
    half = (hi - lo) / 2.0 / scale
    return center - half, center + half
