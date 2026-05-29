"""Spectrogram / heatmap analysis tests."""

import numpy as np
import pytest

from aviz.analysis.spectrogram import compute_spectrogram
from aviz.audio.decoder import load_audio_file
from tests.helpers.sample_audio import SAMPLE_RATE, make_frequency_sweep


def test_spectrogram_shape(sweep_wav):
    audio = load_audio_file(sweep_wav)
    mono = audio.samples.mean(axis=1) if audio.samples.ndim > 1 else audio.samples
    spec = compute_spectrogram(mono, audio.sample_rate, n_fft=1024, hop=256)
    assert spec.db.ndim == 2
    assert spec.db.shape[0] == len(spec.frequencies)
    assert spec.db.shape[1] == len(spec.times)
    assert spec.duration == pytest.approx(audio.duration, rel=0.05)


def test_spectrogram_downsample_time():
    sr = SAMPLE_RATE
    # ~10s of audio
    mono = make_frequency_sweep(10.0)
    spec = compute_spectrogram(mono, sr, n_fft=512, hop=128, max_time_bins=200)
    assert spec.db.shape[1] <= 200


def test_sweep_has_energy_spread(sweep_wav):
    audio = load_audio_file(sweep_wav)
    mono = audio.samples
    spec = compute_spectrogram(mono, audio.sample_rate, n_fft=2048, hop=512)
    # Multiple frequency rows should exceed noise floor
    row_max = spec.db.max(axis=1)
    loud_rows = np.sum(row_max > row_max.max() - 30)
    assert loud_rows > 10
