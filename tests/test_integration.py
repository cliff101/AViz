"""End-to-end pipeline: samples → decode → spectrogram → workspace queue."""

from pathlib import Path

import numpy as np
import pytest

from aviz.analysis.fft import compute_spectrum, resample_log_display
from aviz.analysis.spectrogram import compute_spectrogram
from aviz.audio.decoder import load_audio_file
from aviz.audio.player import AudioPlayer
from aviz.visual_settings import VisualSettings
from aviz.workspace.manager import WorkspaceManager


def test_full_file_analysis_pipeline(sample_paths: dict[str, Path]):
    """Simulates Player load: decode + STFT + live spectrum slice."""
    path = sample_paths["mixed_bands.wav"]
    audio = load_audio_file(path)
    mono = audio.samples.mean(axis=1) if audio.samples.ndim > 1 else audio.samples
    spec = compute_spectrogram(mono, audio.sample_rate)
    assert np.isfinite(spec.db).all()

    # Mini-spectrum at t=0.5s
    i = int(0.5 * audio.sample_rate)
    chunk = mono[max(0, i - 2048) : i + 2048]
    freqs, db = compute_spectrum(chunk, audio.sample_rate, n_fft=2048)
    vis = VisualSettings()
    f_disp, d_disp = resample_log_display(
        freqs, db, vis.freq_min_hz, vis.freq_max_hz, n_points=512
    )
    assert len(f_disp) == 512
    assert d_disp.max() > -120


def test_playlist_queue_order(tmp_workspace: Path, sample_paths: dict[str, Path]):
    """Prev/next queue: three tracks in playlist."""
    mgr = WorkspaceManager()
    mgr.create(tmp_workspace, "Integration")
    names = ["tone_440hz.wav", "chord_major.wav", "melody_arpeggio.wav"]
    entries = mgr.add_files([sample_paths[n] for n in names])
    pl = mgr.current.get_playlist(mgr.current.default_playlist_id)
    pl.file_ids = [e.id for e in entries]

    queue = list(pl.file_ids)
    assert len(queue) == 3
    # Simulate next index
    idx = 0
    idx = min(idx + 1, len(queue) - 1)
    assert idx == 1
    assert mgr.current.get_file(queue[idx]).display_name or Path(
        mgr.current.get_file(queue[idx]).path
    ).name


def test_all_samples_decode_and_spectrogram(sample_paths: dict[str, Path]):
    for name, path in sample_paths.items():
        audio = load_audio_file(path)
        mono = audio.samples if audio.samples.ndim == 1 else audio.samples.mean(axis=1)
        spec = compute_spectrogram(mono, audio.sample_rate, n_fft=1024, hop=256)
        assert spec.db.size > 0, f"Empty spectrogram for {name}"


@pytest.fixture
def mock_sd(monkeypatch):
    class FakeStream:
        def start(self):
            pass

        def stop(self):
            pass

        def close(self):
            pass

    import sounddevice as sd

    monkeypatch.setattr(sd, "OutputStream", lambda **k: FakeStream())


def test_player_load_every_sample_file(mock_sd, sample_paths: dict[str, Path]):
    player = AudioPlayer()
    for path in sample_paths.values():
        player.load(path)
        assert player.duration > 0
