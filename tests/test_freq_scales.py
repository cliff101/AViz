"""Frequency scale modes."""

import numpy as np

from aviz.analysis.fft import compute_spectrum
from aviz.analysis.freq_scales import (
    FREQ_SCALE_OPTIONS,
    finalize_spectrum_display,
    normalize_freq_scale,
    prepare_spectrum_display,
    target_display_points,
    uses_warped_x_axis,
)
def test_mel_is_restored():
    assert normalize_freq_scale("mel") == "mel"
    assert "mel" in {o[0] for o in FREQ_SCALE_OPTIONS}


def test_legacy_bark_maps_to_mel():
    assert normalize_freq_scale("bark") == "mel"


def test_focus_uses_warped_axis():
    assert uses_warped_x_axis("focus")
    assert not uses_warped_x_axis("mel")


def test_mel_returns_hz_coordinates():
    sr = 48_000
    t = np.arange(4096) / sr
    s = np.sin(2 * np.pi * 440 * t)
    freqs, db = compute_spectrum(s, sr, n_fft=2048)
    x, d, _, hz = prepare_spectrum_display(
        freqs, db, sr, "mel", 20, 12_000
    )
    assert len(x) == 80
    np.testing.assert_allclose(x, hz)


def test_focus_returns_unit_interval_x():
    sr = 48_000
    t = np.arange(4096) / sr
    s = np.sin(2 * np.pi * 440 * t)
    freqs, db = compute_spectrum(s, sr, n_fft=2048)
    x, d, _, hz = prepare_spectrum_display(
        freqs, db, sr, "focus", 20, 12_000
    )
    assert x.max() <= 1.0 + 1e-6
    assert hz.max() > x.max()


def test_mel_not_upsampled_to_512():
    sr = 48_000
    t = np.arange(4096) / sr
    s = np.sin(2 * np.pi * 440 * t)
    freqs, db = compute_spectrum(s, sr, n_fft=512)
    x, d, _, hz = prepare_spectrum_display(freqs, db, sr, "mel", 20, 12_000)
    x, d, hz, _, _ = finalize_spectrum_display(
        x, d, hz, None, scale="mel", smoothing_freq=0, smooth_state=None
    )
    assert len(x) == 80


def test_small_fft_linear_keeps_bin_count():
    sr = 48_000
    t = np.arange(4096) / sr
    s = np.sin(2 * np.pi * 440 * t)
    freqs, db = compute_spectrum(s, sr, n_fft=512)
    x, d, _, hz = prepare_spectrum_display(freqs, db, sr, "linear", 20, 12_000)
    n = target_display_points("linear", len(x))
    assert n == len(x)
    x, d, hz, _, _ = finalize_spectrum_display(
        x, d, hz, None, scale="linear", smoothing_freq=0, smooth_state=None
    )
    assert len(x) == len(freqs[(freqs >= 20) & (freqs <= 12_000)])


def test_focus_uniform_display_spacing():
    sr = 48_000
    t = np.arange(4096) / sr
    s = np.sin(2 * np.pi * 440 * t)
    freqs, db = compute_spectrum(s, sr, n_fft=512)
    x, d, _, hz = prepare_spectrum_display(
        freqs, db, sr, "focus", 20, 12_000
    )
    assert len(x) == target_display_points("focus", len(freqs[(freqs >= 20) & (freqs <= 12_000)]))
    dx = np.diff(x)
    np.testing.assert_allclose(dx, dx[0], rtol=1e-5, atol=1e-9)
