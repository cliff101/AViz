"""Frequency axis ticks for mel / focus / log / linear scales."""

from __future__ import annotations

import math

import numpy as np
import pyqtgraph as pg
from numpy.typing import NDArray

from aviz.analysis.freq_scales import (
    focus_tick_pairs,
    normalize_freq_scale,
    uses_warped_x_axis,
)

_SCALE_AXIS_LABEL: dict[str, str] = {
    "mel": "Hz · mel bands",
    "focus": "Hz (lows expanded)",
    "log": "Hz · log",
    "linear": "Hz · linear",
}


def axis_label_for_scale(scale: str) -> str:
    return _SCALE_AXIS_LABEL.get(normalize_freq_scale(scale), "Hz")


def nice_hz_tick_values(
    f_min: float,
    f_max: float,
    *,
    max_ticks: int = 9,
) -> list[float]:
    f_min = max(float(f_min), 1.0)
    f_max = max(float(f_max), f_min + 1.0)
    exp_lo = int(math.floor(math.log10(f_min)))
    exp_hi = int(math.ceil(math.log10(f_max)))
    candidates: list[float] = []
    for exp in range(exp_lo, exp_hi + 1):
        for mant in (1, 2, 5):
            v = mant * (10.0**exp)
            if f_min <= v <= f_max:
                candidates.append(v)
    if not candidates:
        return [f_min, f_max]
    if len(candidates) <= max_ticks:
        return candidates
    idx = np.linspace(0, len(candidates) - 1, max_ticks).astype(int)
    return [candidates[i] for i in np.unique(idx)]


def band_tick_values(
    centers_hz: NDArray[np.float64],
    *,
    max_ticks: int = 9,
) -> list[float]:
    if len(centers_hz) == 0:
        return []
    if len(centers_hz) <= max_ticks:
        return [float(x) for x in centers_hz]
    idx = np.linspace(0, len(centers_hz) - 1, max_ticks).astype(int)
    return [float(centers_hz[i]) for i in np.unique(idx)]


def format_hz_tick(value: float) -> str:
    v = float(value)
    if v >= 10_000:
        return f"{v / 1000:.0f}k"
    if v >= 1000:
        return f"{v / 1000:.1f}k".replace(".0k", "k")
    return f"{v:.0f}"


class FrequencyScaleAxis(pg.AxisItem):
    """Bottom axis — tick positions match the active frequency scale."""

    def configure(
        self,
        scale: str,
        *,
        f_min: float = 20.0,
        f_max: float = 12_000.0,
        display_hz: NDArray[np.float64] | None = None,
    ) -> None:
        scale = normalize_freq_scale(scale)
        if scale == "log":
            self.setTicks(None)
            return
        if uses_warped_x_axis(scale):
            major = [
                (x, format_hz_tick(hz)) for x, hz in focus_tick_pairs(f_min, f_max)
            ]
            self.setTicks([major, []])
            return
        if scale == "mel" and display_hz is not None and len(display_hz) >= 2:
            ticks = band_tick_values(display_hz)
            major = [(t, format_hz_tick(t)) for t in ticks]
            self.setTicks([major, []])
            return
        ticks = nice_hz_tick_values(f_min, f_max)
        major = [(t, format_hz_tick(t)) for t in ticks]
        self.setTicks([major, []])
