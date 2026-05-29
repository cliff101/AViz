"""Live loopback tests — require audio playing on default output.

Run manually while music is playing:
    pytest tests/test_loopback_live.py -m hardware -s

Skip in CI (default):
    pytest -m "not hardware"
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from aviz.analysis.fft import compute_spectrum
from aviz.audio.capture import LoopbackCapture, list_loopback_devices

pytestmark = pytest.mark.hardware


def _devices_or_skip():
    devices = list_loopback_devices()
    if not devices:
        pytest.skip("PyAudioWPatch not installed or no WASAPI loopback devices")
    return devices


@pytest.mark.hardware
def test_list_loopback_devices():
    devices = _devices_or_skip()
    assert len(devices) >= 1
    assert all(d.is_loopback for d in devices)


@pytest.mark.hardware
def test_loopback_receives_signal_while_playing():
    """Probe all loopback devices; pass if any receives music-level signal."""
    devices = _devices_or_skip()
    best_rms = 0.0
    best_name = ""
    best_audio = None
    best_sr = 48000

    for d in devices:
        cap = LoopbackCapture(device_index=d.index)
        cap.start()
        time.sleep(0.2)
        chunks = []
        deadline = time.time() + 2.0
        while time.time() < deadline:
            c = cap.read(timeout=0.12)
            if c is not None and len(c):
                chunks.append(c)
        cap.stop()
        if not chunks:
            continue
        audio = np.concatenate(chunks)
        rms = float(np.sqrt(np.mean(audio**2)))
        if rms > best_rms:
            best_rms = rms
            best_name = d.name
            best_audio = audio
            best_sr = cap.sample_rate

    if best_audio is None or best_rms < 0.0005:
        pytest.fail(
            "No loopback device received audio. Play music on your speakers/headphones "
            "and run: pytest tests/test_loopback_live.py -m hardware -s"
        )

    freqs, db = compute_spectrum(best_audio[-4096:], best_sr, n_fft=2048)
    assert len(freqs) > 100
    assert float(db.max()) > -50, (
        f"Spectrum weak on best device {best_name!r} (RMS={best_rms:.4f})"
    )
