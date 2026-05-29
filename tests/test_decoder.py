"""Audio file decoder tests."""

from pathlib import Path

import numpy as np
import pytest

from aviz.audio.decoder import load_audio_file


def test_load_tone(tone_wav: Path):
    audio = load_audio_file(tone_wav)
    assert audio.sample_rate == 48000
    assert audio.duration > 0.5
    assert audio.channels >= 1
    assert audio.path == tone_wav.resolve()


def test_load_stereo_from_samples(sample_paths: dict[str, Path]):
    path = sample_paths["stereo_pan.wav"]
    audio = load_audio_file(path)
    assert audio.channels == 2
    assert audio.samples.shape[1] == 2


def test_load_melody_metadata(melody_wav: Path):
    audio = load_audio_file(melody_wav)
    assert audio.duration == pytest.approx(3.0, abs=0.2)
    assert len(audio.samples) > 100000


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(Exception):
        load_audio_file(tmp_path / "nope.wav")


def test_mono_shape(tone_wav: Path):
    audio = load_audio_file(tone_wav)
    assert audio.samples.ndim in (1, 2)
    peak = np.abs(audio.samples).max()
    assert 0 < peak <= 1.5
