"""Real-time and block FFT analysis."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from aviz.analysis._scipy_compat import get_window, rfft, rfftfreq


def bin_frequencies(n_fft: int, sample_rate: float) -> NDArray[np.float64]:
    """Hz for each positive-frequency FFT bin."""
    return rfftfreq(n_fft, d=1.0 / sample_rate)


def compute_spectrum(
    samples: NDArray[np.float64],
    sample_rate: float,
    n_fft: int | None = None,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """
    Windowed RFFT → frequencies (Hz) and magnitudes in dB for all bins.
    samples: mono float, any length (will be padded/truncated to n_fft).
    """
    n = n_fft or min(2048, max(256, len(samples)))
    if len(samples) < n:
        buf = np.zeros(n, dtype=np.float64)
        buf[: len(samples)] = samples
    else:
        buf = samples[-n:].astype(np.float64)

    window = get_window("hann", n, fftbins=True)
    windowed = buf * window
    spectrum = rfft(windowed, n=n)
    magnitudes = np.abs(spectrum)
    magnitudes = np.maximum(magnitudes, 1e-12)
    db = 20.0 * np.log10(magnitudes)
    freqs = rfftfreq(n, d=1.0 / sample_rate)
    return freqs, db


def smooth_spectrum(
    db: NDArray[np.float64],
    alpha: float,
    state: NDArray[np.float64] | None,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Per-bin temporal EMA (legacy); prefer smooth_spectrum_display on plot coordinates."""
    if state is None or len(state) != len(db):
        state = db.copy()
    else:
        state = alpha * db + (1.0 - alpha) * state
    return state, state


def fill_display_gaps(y: NDArray[np.float64], *, floor_db: float = -80.0) -> NDArray[np.float64]:
    """Public wrapper: empty / NaN bins → average of nearest valid neighbors."""
    return _fill_nan_1d(y, fill=floor_db)


def _fill_nan_1d(y: NDArray[np.float64], *, fill: float = -80.0) -> NDArray[np.float64]:
    """Fill empty bins with the average of nearest valid neighbors (never the dB floor)."""
    out = np.asarray(y, dtype=np.float64).copy()
    # Bins at/below the visual floor are "no data" (empty mel bands, FFT noise).
    gap = ~np.isfinite(out) | (out <= fill + 1e-3)
    out[gap] = np.nan
    valid = np.isfinite(out)
    if np.all(valid):
        return out
    if not np.any(valid):
        out[:] = fill
        return out

    n = len(out)
    idx = np.arange(n, dtype=np.intp)
    fwd_i = np.maximum.accumulate(np.where(valid, idx, -1))
    bwd_i = np.minimum.accumulate(np.where(valid, idx, n)[::-1])[::-1]

    empty = ~valid
    empty_idx = np.flatnonzero(empty)
    has_left = fwd_i[empty] >= 0
    has_right = bwd_i[empty] < n

    both = empty_idx[has_left & has_right]
    if len(both):
        out[both] = 0.5 * (out[fwd_i[both]] + out[bwd_i[both]])

    left_only = empty_idx[has_left & ~has_right]
    if len(left_only):
        out[left_only] = out[fwd_i[left_only]]

    right_only = empty_idx[~has_left & has_right]
    if len(right_only):
        out[right_only] = out[bwd_i[right_only]]

    still = ~np.isfinite(out)
    if np.any(still):
        out[still] = fill
    return out


_BIN_GEOMETRY_CACHE: dict[tuple[float, float, int, bool], tuple[np.ndarray, np.ndarray]] = {}
_SPATIAL_KERNELS: dict[int, NDArray[np.float64]] = {}


def _bin_geometry(
    x0: float,
    x1: float,
    n_points: int,
    plot_hz_from_log: bool,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    key = (round(x0, 5), round(x1, 5), n_points, plot_hz_from_log)
    cached = _BIN_GEOMETRY_CACHE.get(key)
    if cached is not None:
        return cached
    edges = np.linspace(x0, x1, n_points + 1, dtype=np.float64)
    centers = 0.5 * (edges[:-1] + edges[1:])
    plot_x = np.power(10.0, centers) if plot_hz_from_log else centers
    _BIN_GEOMETRY_CACHE[key] = (edges, plot_x)
    if len(_BIN_GEOMETRY_CACHE) > 32:
        _BIN_GEOMETRY_CACHE.clear()
    return edges, plot_x


def _bin_aggregate(
    idx: NDArray[np.intp],
    values: NDArray[np.float64],
    n_points: int,
    *,
    aggregate: str,
    fill: float,
) -> NDArray[np.float64]:
    if aggregate == "max":
        out = np.full(n_points, -np.inf, dtype=np.float64)
        np.maximum.at(out, idx, values)
        empty = ~np.isfinite(out) | (out == -np.inf)
        out[empty] = np.nan
        return _fill_nan_1d(out, fill=fill)
    counts = np.bincount(idx, minlength=n_points)
    sums = np.bincount(idx, weights=values, minlength=n_points)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = sums / counts
    out[counts == 0] = np.nan
    return _fill_nan_1d(out, fill=fill)


def resample_uniform_display(
    x_bin: NDArray[np.float64],
    db: NDArray[np.float64],
    hz: NDArray[np.float64] | None = None,
    *,
    n_points: int = 512,
    aggregate: str = "mean",
    plot_hz_from_log: bool = False,
    peaks: NDArray[np.float64] | None = None,
    floor_db: float = -80.0,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64] | None,
    NDArray[np.float64] | None,
]:
    """
    Bin onto equal-width display coordinates (linear on-screen density).
    Vectorized; optional peaks use the same bin indices in one pass.
    """
    if len(x_bin) < 2 or n_points < 2:
        return x_bin, db, hz, peaks

    xs = np.ascontiguousarray(x_bin, dtype=np.float64)
    ds = np.ascontiguousarray(db, dtype=np.float64)
    if xs[1] < xs[0]:
        order = np.argsort(xs, kind="stable")
        xs = xs[order]
        ds = ds[order]
        hz_s = hz[order] if hz is not None and len(hz) == len(x_bin) else None
        pk = peaks[order] if peaks is not None and len(peaks) == len(x_bin) else None
    else:
        hz_s = hz
        pk = peaks

    x0, x1 = float(xs[0]), float(xs[-1])
    if x1 <= x0 + 1e-12:
        return x_bin, db, hz, peaks

    edges, plot_x = _bin_geometry(x0, x1, n_points, plot_hz_from_log)
    idx = np.digitize(xs, edges[1:-1], right=False)
    np.clip(idx, 0, n_points - 1, out=idx)

    d_out = _bin_aggregate(idx, ds, n_points, aggregate=aggregate, fill=floor_db)
    p_out: NDArray[np.float64] | None = None
    if pk is not None:
        p_out = _bin_aggregate(idx, pk, n_points, aggregate="max", fill=floor_db)

    if hz_s is not None and len(hz_s) == len(xs):
        hz_out = _bin_aggregate(
            idx, hz_s, n_points, aggregate="mean", fill=float(np.min(hz_s))
        )
    else:
        hz_out = plot_x.copy()

    return plot_x, d_out, hz_out, p_out


def upsample_display_curve(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    hz: NDArray[np.float64] | None = None,
    *,
    factor: int = 2,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64] | None]:
    """Denser plot polyline from an already-smoothed display grid."""
    if factor <= 1 or len(x) < 2:
        return x, y, hz
    n = len(x) * factor
    xu = np.linspace(float(x[0]), float(x[-1]), n)
    yu = np.interp(xu, x, y)
    hu = np.interp(xu, x, hz) if hz is not None and len(hz) == len(x) else None
    return xu, yu, hu


def spatial_smooth_display(
    db: NDArray[np.float64],
    smoothing_freq: float,
) -> NDArray[np.float64]:
    """Along-display spatial blur; width is constant in plot X (matches frequency scale)."""
    if smoothing_freq <= 0 or len(db) < 3:
        return db
    k = min(31, max(3, int(1.0 + smoothing_freq * 14.0) | 1))
    kernel = _SPATIAL_KERNELS.get(k)
    if kernel is None:
        sigma = max(k / 6.0, 0.5)
        x = np.arange(k, dtype=np.float64) - (k // 2)
        kernel = np.exp(-0.5 * (x / sigma) ** 2)
        kernel /= kernel.sum()
        _SPATIAL_KERNELS[k] = kernel
    pad = k // 2
    padded = np.pad(db.astype(np.float64, copy=False), (pad, pad), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def smooth_spectrum_display(
    x: NDArray[np.float64],
    db: NDArray[np.float64],
    alpha: float,
    state: NDArray[np.float64] | None,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Temporal EMA on the uniform display grid (after binning / spatial smooth)."""
    if state is None or len(state) != len(db):
        state = db.copy()
    else:
        state = alpha * db + (1.0 - alpha) * state
    return x, state, state


def smooth_temporal(
    db: NDArray[np.float64],
    alpha: float,
    state: NDArray[np.float64] | None,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    if state is None or len(state) != len(db):
        state = db.copy()
    else:
        state = alpha * db + (1.0 - alpha) * state
    return state, state


def peak_hold(
    db: NDArray[np.float64],
    peaks: NDArray[np.float64] | None,
    decay: float,
) -> NDArray[np.float64]:
    """Per-frequency peak hold with decay toward current value."""
    if peaks is None or len(peaks) != len(db):
        return db.copy()
    peaks = np.maximum(db, peaks - decay)
    return peaks


def resample_log_display(
    freqs: NDArray[np.float64],
    db: NDArray[np.float64],
    f_min: float,
    f_max: float,
    n_points: int = 512,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Resample spectrum onto log-spaced Hz axis for display."""
    mask = (freqs >= f_min) & (freqs <= f_max)
    f = freqs[mask]
    d = db[mask]
    if len(f) < 2:
        log_f = np.logspace(np.log10(max(f_min, 1)), np.log10(f_max), n_points)
        return log_f, np.full(n_points, -80.0)
    log_f = np.logspace(np.log10(f_min), np.log10(f_max), n_points)
    db_interp = np.interp(log_f, f, d, left=d[0], right=d[-1])
    return log_f, db_interp


def mel_filterbank_display(
    freqs: NDArray[np.float64],
    db: NDArray[np.float64],
    sample_rate: float,
    n_mels: int = 64,
    f_min: float = 20.0,
    f_max: float | None = None,
    aggregate: str = "mean",
    floor_db: float = -50.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Simple mel-spaced bin aggregation for display (mean or max per band)."""
    f_max = f_max or sample_rate / 2
    mel_min = _hz_to_mel(f_min)
    mel_max = _hz_to_mel(f_max)
    mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
    hz_points = _mel_to_hz(mel_points)
    out_db = np.full(n_mels, np.nan, dtype=np.float64)
    centers = np.zeros(n_mels)
    for i in range(n_mels):
        lo, hi = hz_points[i], hz_points[i + 2]
        m = (freqs >= lo) & (freqs < hi)
        centers[i] = (lo + hi) / 2
        if np.any(m):
            out_db[i] = float(np.max(db[m]) if aggregate == "max" else np.mean(db[m]))
    return centers, fill_display_gaps(out_db, floor_db=floor_db)


def _hz_to_mel(hz: float) -> float:
    return 2595.0 * np.log10(1.0 + hz / 700.0)


def _mel_to_hz(mel: NDArray[np.float64]) -> NDArray[np.float64]:
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)
