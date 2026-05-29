"""Frequency scale modes for the live spectrum."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from aviz.analysis.fft import (
    _hz_to_mel,
    _mel_to_hz,
    fill_display_gaps,
    mel_filterbank_display,
    resample_log_display,
    resample_uniform_display,
    smooth_spectrum_display,
    spatial_smooth_display,
    upsample_display_curve,
)

_DISPLAY_POINTS = 512
# Focus always gets at least this much spatial + temporal polish on the display grid.
_FOCUS_MIN_SMOOTH = 0.38
_FOCUS_UPSAMPLE = 1  # 512 pts; 2× was smoother but costly for live redraw

# (id, UI label)
FREQ_SCALE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("mel", "Mel (pitch bands)"),
    ("focus", "Focus (lows wide)"),
    ("log", "Log Hz (analyzer)"),
    ("linear", "Linear Hz"),
)

VALID_FREQ_SCALES = frozenset(opt[0] for opt in FREQ_SCALE_OPTIONS)

# Removed scales → nearest replacement
_LEGACY_SCALE_MAP = {
    "bark": "mel",
    "perceptual": "mel",
    "sqrt": "focus",
}


def normalize_freq_scale(scale: str) -> str:
    return _LEGACY_SCALE_MAP.get(scale, scale if scale in VALID_FREQ_SCALES else "mel")


def uses_warped_x_axis(scale: str) -> bool:
    """True when plot X is 0..1 (focus); False when X is Hz (mel / log / linear)."""
    return normalize_freq_scale(scale) == "focus"


def _mel_vec(hz: NDArray[np.float64]) -> NDArray[np.float64]:
    return 2595.0 * np.log10(1.0 + np.maximum(hz, 1.0) / 700.0)


def hz_to_focus_x(
    freqs_hz: NDArray[np.float64],
    f_min: float,
    f_max: float,
) -> NDArray[np.float64]:
    """Map Hz → [0, 1] so lows use most of the horizontal space (mel warp)."""
    m = _mel_vec(freqs_hz)
    m0 = _hz_to_mel(max(f_min, 1.0))
    m1 = _hz_to_mel(max(f_max, f_min + 1.0))
    span = max(m1 - m0, 1e-9)
    return np.clip((m - m0) / span, 0.0, 1.0)


def focus_tick_pairs(
    f_min: float,
    f_max: float,
    *,
    n: int = 8,
) -> list[tuple[float, float]]:
    """(display_x, hz) for axis labels under focus scale."""
    m0 = _hz_to_mel(max(f_min, 1.0))
    m1 = _hz_to_mel(max(f_max, f_min + 1.0))
    mel_lin = np.linspace(0.0, 1.0, n)
    m = m0 + mel_lin * (m1 - m0)
    hz = _mel_to_hz(m)
    return [(float(x), float(h)) for x, h in zip(mel_lin, hz)]


def prepare_spectrum_display(
    freqs: NDArray[np.float64],
    db: NDArray[np.float64],
    sample_rate: float,
    scale: str,
    f_min: float,
    f_max: float,
    floor_db: float = -50.0,
    peaks: NDArray[np.float64] | None = None,
    *,
    n_log_points: int = 512,
    n_mels: int = 80,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64] | None, NDArray[np.float64]]:
    """
    Returns (x_plot, db, peaks, hz).
    x_plot is the coordinate drawn on the chart; hz is true frequency (ticks / peak Hz).
    """
    scale = normalize_freq_scale(scale)
    p_disp: NDArray[np.float64] | None = None

    if scale == "log":
        hz, d_disp = resample_log_display(
            freqs, db, f_min, f_max, n_points=n_log_points
        )
        if peaks is not None:
            _, p_disp = resample_log_display(
                freqs, peaks, f_min, f_max, n_points=n_log_points
            )
        return hz, d_disp, p_disp, hz

    if scale == "mel":
        hz, d_disp = mel_filterbank_display(
            freqs,
            db,
            sample_rate,
            n_mels=n_mels,
            f_min=f_min,
            f_max=f_max,
            floor_db=floor_db,
        )
        if peaks is not None:
            _, p_disp = mel_filterbank_display(
                freqs,
                peaks,
                sample_rate,
                n_mels=n_mels,
                f_min=f_min,
                f_max=f_max,
                aggregate="max",
                floor_db=floor_db,
            )
        return hz, d_disp, p_disp, hz

    if scale == "focus":
        mask = (freqs >= f_min) & (freqs <= f_max)
        hz = freqs[mask]
        d_disp = db[mask]
        x = hz_to_focus_x(hz, f_min, f_max)
        pk = peaks[mask] if peaks is not None and len(peaks) == len(freqs) else None
        n_disp = target_display_points("focus", len(x))
        x, d_disp, hz, p_disp = resample_uniform_display(
            x, d_disp, hz, n_points=n_disp, peaks=pk, floor_db=floor_db
        )
        return x, d_disp, p_disp, hz

    # linear
    mask = (freqs >= f_min) & (freqs <= f_max)
    hz, d_disp = freqs[mask], db[mask]
    if peaks is not None:
        p_disp = peaks[mask] if len(peaks) == len(freqs) else peaks
    return hz, d_disp, p_disp, hz


def target_display_points(scale: str, n_in: int) -> int:
    """Match display resolution to real bins — avoid upsampling sparse data to 512."""
    scale = normalize_freq_scale(scale)
    if scale == "mel":
        return max(n_in, 2)
    if scale == "log":
        return n_in if n_in >= 256 else _DISPLAY_POINTS
    # focus / linear: never invent more points than we have
    return min(_DISPLAY_POINTS, max(n_in, 64))


def needs_uniform_resample(scale: str, n_in: int, n_points: int | None = None) -> bool:
    """Re-bin only when merging oversampled bins onto a smaller display grid."""
    if n_in < 2:
        return False
    scale = normalize_freq_scale(scale)
    if scale == "mel":
        return False
    n_tgt = n_points if n_points is not None else target_display_points(scale, n_in)
    if n_in == n_tgt:
        return False
    return n_in > n_tgt


def display_bin_coordinates(
    scale: str,
    x_plot: NDArray[np.float64],
    hz: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Coordinates for equal on-screen density: bin in x_bin, draw at x_plot."""
    scale = normalize_freq_scale(scale)
    if scale == "focus":
        return x_plot, x_plot
    if scale == "log":
        return np.log10(np.maximum(hz, 1.0)), hz
    return hz, hz


def finalize_spectrum_display(
    x_plot: NDArray[np.float64],
    db: NDArray[np.float64],
    hz: NDArray[np.float64],
    peaks: NDArray[np.float64] | None,
    *,
    scale: str,
    smoothing_freq: float,
    smooth_state: NDArray[np.float64] | None,
    n_points: int = _DISPLAY_POINTS,
    floor_db: float = -80.0,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64] | None,
    NDArray[np.float64] | None,
]:
    """
    Equal display-X density for every frequency scale (incl. Focus).
    Bins merge oversampled regions; freq smooth is spatial + temporal on that grid.
    """
    scale = normalize_freq_scale(scale)
    if len(x_plot) < 2:
        return x_plot, db, hz, peaks, smooth_state

    log_plot = scale == "log"
    n_tgt = target_display_points(scale, len(x_plot))
    if needs_uniform_resample(scale, len(x_plot), n_tgt):
        x_bin, _ = display_bin_coordinates(scale, x_plot, hz)
        pk = peaks if peaks is not None and len(peaks) == len(x_bin) else None
        x_plot, db, hz, peaks = resample_uniform_display(
            x_bin,
            db,
            hz,
            n_points=n_tgt,
            aggregate="mean",
            plot_hz_from_log=log_plot,
            peaks=pk,
            floor_db=floor_db,
        )

    if scale == "focus":
        eff = max(smoothing_freq, _FOCUS_MIN_SMOOTH)
        db = spatial_smooth_display(db, eff)
        if peaks is not None:
            peaks = spatial_smooth_display(peaks, max(eff * 0.7, 0.28))
        alpha = max(0.15, 1.0 - max(smoothing_freq, 0.28))
        x_plot, db, smooth_state = smooth_spectrum_display(
            x_plot, db, alpha, smooth_state
        )
        x_base = x_plot
        x_plot, db, hz = upsample_display_curve(
            x_base, db, hz, factor=_FOCUS_UPSAMPLE
        )
        if peaks is not None:
            _, peaks, _ = upsample_display_curve(
                x_base, peaks, hz, factor=_FOCUS_UPSAMPLE
            )
    elif smoothing_freq > 0:
        db = spatial_smooth_display(db, smoothing_freq)
        alpha = max(0.05, 1.0 - smoothing_freq)
        x_plot, db, smooth_state = smooth_spectrum_display(
            x_plot, db, alpha, smooth_state
        )

    db = fill_display_gaps(db, floor_db=floor_db)
    if peaks is not None:
        peaks = fill_display_gaps(peaks, floor_db=floor_db)

    return x_plot, db, hz, peaks, smooth_state
