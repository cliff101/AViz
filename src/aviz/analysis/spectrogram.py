"""Offline STFT spectrogram for file heatmaps."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from aviz.analysis._scipy_compat import spectrogram as scipy_spectrogram


@dataclass
class SpectrogramResult:
    times: NDArray[np.float64]
    frequencies: NDArray[np.float64]
    db: NDArray[np.float64]  # shape (n_freq, n_time)
    sample_rate: float
    duration: float


def compute_spectrogram(
    samples: NDArray[np.float64],
    sample_rate: float,
    n_fft: int = 2048,
    hop: int = 512,
    max_time_bins: int = 2000,
) -> SpectrogramResult:
    """STFT magnitude in dB; optionally downsample time axis for display."""
    mono = _to_mono(samples)
    freqs, times, Sxx = scipy_spectrogram(
        mono,
        fs=sample_rate,
        window="hann",
        nperseg=n_fft,
        noverlap=n_fft - hop,
        mode="magnitude",
    )
    db = 20.0 * np.log10(np.maximum(Sxx, 1e-12))

    if db.shape[1] > max_time_bins:
        factor = int(np.ceil(db.shape[1] / max_time_bins))
        n_t = db.shape[1] // factor
        trimmed = db[:, : n_t * factor]
        db = trimmed.reshape(db.shape[0], n_t, factor).max(axis=2)
        times = times[: n_t * factor:factor]

    duration = len(mono) / sample_rate
    return SpectrogramResult(
        times=times,
        frequencies=freqs,
        db=db,
        sample_rate=sample_rate,
        duration=duration,
    )


def _to_mono(samples: NDArray[np.float64]) -> NDArray[np.float64]:
    if samples.ndim == 1:
        return samples.astype(np.float64)
    return samples.mean(axis=1).astype(np.float64)
