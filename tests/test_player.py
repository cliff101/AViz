"""Audio player tests (sounddevice mocked)."""

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import sounddevice as sd

from aviz.audio.decoder import load_audio_file
from aviz.audio.player import AudioPlayer


@pytest.fixture
def mock_output_stream(monkeypatch):
    class FakeStream:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def start(self):
            pass

        def stop(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(sd, "OutputStream", FakeStream)


def test_load_and_duration(tone_wav: Path, mock_output_stream):
    player = AudioPlayer()
    audio = player.load(tone_wav)
    assert player.duration == pytest.approx(audio.duration, rel=0.01)
    assert player.position == 0.0
    assert not player.is_playing


def test_play_pause(mock_output_stream, tone_wav: Path):
    player = AudioPlayer()
    player.load(tone_wav)
    player.play()
    assert player.is_playing
    player.pause()
    assert not player.is_playing


def test_seek(mock_output_stream, tone_wav: Path):
    player = AudioPlayer()
    player.load(tone_wav)
    player.seek(0.5)
    assert player.position == pytest.approx(0.5, abs=0.05)


def test_toggle_restarts_at_end(mock_output_stream, tone_wav: Path):
    player = AudioPlayer()
    audio = player.load(tone_wav)
    mono_len = len(audio.samples) if audio.samples.ndim == 1 else len(audio.samples)
    player._position = mono_len
    player.toggle()
    assert player._position == 0


def test_load_audio_in_memory(mock_output_stream, tone_wav: Path):
    player = AudioPlayer()
    audio = load_audio_file(tone_wav)
    player.load_audio(audio)
    assert player.audio is audio
