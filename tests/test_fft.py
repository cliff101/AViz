"""FFT / spectrum analysis tests."""

import numpy as np
import pytest

from aviz.analysis.fft import (
    bin_frequencies,
    compute_spectrum,
    mel_filterbank_display,
    peak_hold,
    resample_log_display,
    smooth_spectrum,
    smooth_temporal,
)
from tests.helpers.sample_audio import SAMPLE_RATE, make_tone_440hz, sine_tone


def test_spectrum_many_bins():
    samples = make_tone_440hz(0.1)
    freqs, db = compute_spectrum(samples, SAMPLE_RATE, n_fft=2048)
    assert len(freqs) == len(db)
    assert len(freqs) > 100
    peak_i = np.argmax(db)
    assert 400 < freqs[peak_i] < 480


def test_bin_frequencies_spacing():
    f = bin_frequencies(2048, 48000)
    assert f[1] - f[0] == pytest.approx(48000 / 2048)


def test_dual_tone_two_peaks():
    sr = SAMPLE_RATE
    t = np.arange(4096) / sr
    samples = np.sin(2 * np.pi * 300 * t) + np.sin(2 * np.pi * 3000 * t)
    freqs, db = compute_spectrum(samples, sr, n_fft=2048)
    # Energy present in low and high bands
    low = db[(freqs > 250) & (freqs < 350)].max()
    high = db[(freqs > 2800) & (freqs < 3200)].max()
    assert low > -40
    assert high > -40


def test_resample_log_display_length():
    samples = make_tone_440hz(0.1)
    freqs, db = compute_spectrum(samples, SAMPLE_RATE, n_fft=2048)
    lf, ld = resample_log_display(freqs, db, 20, 20000, n_points=512)
    assert len(lf) == 512
    assert len(ld) == 512
    assert lf[0] == pytest.approx(20, rel=0.01)
    assert lf[-1] == pytest.approx(20000, rel=0.01)


def test_mel_filterbank_bins():
    samples = make_tone_440hz(0.1)
    freqs, db = compute_spectrum(samples, SAMPLE_RATE, n_fft=2048)
    centers, mel_db = mel_filterbank_display(freqs, db, SAMPLE_RATE, n_mels=40)
    assert len(centers) == 40
    assert len(mel_db) == 40


def test_mel_filterbank_max_aggregate():
    samples = make_tone_440hz(0.1)
    freqs, db = compute_spectrum(samples, SAMPLE_RATE, n_fft=2048)
    _, mel_mean = mel_filterbank_display(freqs, db, SAMPLE_RATE, n_mels=40)
    _, mel_max = mel_filterbank_display(
        freqs, db, SAMPLE_RATE, n_mels=40, aggregate="max"
    )
    assert np.max(mel_max) >= np.max(mel_mean) - 0.01


def test_mel_empty_bands_use_neighbor_average():
    from aviz.analysis.fft import mel_filterbank_display

    sr = 48_000
    freqs = np.linspace(0, sr / 2, 257)
    db = np.full(257, -50.0)
    # Only high-frequency bins have energy
    db[freqs >= 2000] = -20.0
    _, mel_db = mel_filterbank_display(freqs, db, sr, n_mels=8, f_min=20, f_max=12_000)
    assert np.all(mel_db > -50.0)
    assert mel_db[0] == pytest.approx(mel_db[-1], rel=0.01)


def test_fill_nan_neighbor_average():
    from aviz.analysis.fft import _fill_nan_1d

    y = np.array([1.0, np.nan, np.nan, 5.0])
    out = _fill_nan_1d(y, fill=-80.0)
    assert out[0] == 1.0
    assert out[1] == pytest.approx(3.0)
    assert out[2] == pytest.approx(3.0)
    assert out[3] == 5.0


def test_smooth_and_peak_hold():
    db = np.array([-60.0, -50.0, -40.0])
    out, state = smooth_spectrum(db, 0.5, None)
    assert state is not None
    out2, _ = smooth_temporal(db, 0.5, state)
    assert len(out2) == 3
    peaks = peak_hold(db, None, 1.0)
    assert np.all(peaks >= db - 0.01)


def test_short_buffer_padded():
    freqs, db = compute_spectrum(np.array([0.0, 0.1]), SAMPLE_RATE, n_fft=512)
    assert len(freqs) == 257
