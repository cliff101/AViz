#!/usr/bin/env python3
"""
Live loopback diagnostic — run while audio is playing on speakers.

Usage:
    python scripts/test_loopback_live.py
    python scripts/test_loopback_live.py --device-index 12
    python scripts/test_loopback_live.py --seconds 5
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np

from aviz.analysis.fft import compute_spectrum, resample_log_display
from aviz.audio.capture import LoopbackCapture, list_loopback_devices


def main() -> int:
    parser = argparse.ArgumentParser(description="Test WASAPI loopback capture")
    parser.add_argument("--device-index", type=int, default=None, help="Loopback device index")
    parser.add_argument("--seconds", type=float, default=4.0, help="Capture duration")
    parser.add_argument("--rms-threshold", type=float, default=0.001, help="Min RMS for pass")
    args = parser.parse_args()

    devices = list_loopback_devices()
    if not devices:
        print("FAIL: No loopback devices found. Install: pip install PyAudioWPatch")
        return 1

    print("Loopback devices:")
    for d in devices:
        print(f"  [{d.index}] {d.name}")

    idx = args.device_index
    if idx is None:
        idx = devices[0].index
        print(f"\nUsing first device: [{idx}] {devices[0].name}")
    else:
        print(f"\nUsing device index: {idx}")

    cap = LoopbackCapture(device_index=idx)
    cap.start()
    time.sleep(0.3)

    if not cap.running:
        print("FAIL: Capture thread did not start (check PyAudioWPatch / device index)")
        return 1

    sr = cap.sample_rate
    print(f"Sample rate: {sr} Hz")
    print(f"Capturing {args.seconds:.1f}s — play audio on that output now…\n")

    chunks: list[np.ndarray] = []
    deadline = time.time() + args.seconds
    while time.time() < deadline:
        chunk = cap.read(timeout=0.2)
        if chunk is not None and len(chunk):
            chunks.append(chunk)

    cap.stop()

    if not chunks:
        print("FAIL: No audio chunks received from loopback.")
        print("  - Confirm music/video is playing on the selected output")
        print("  - Try another device index from the list above")
        return 1

    audio = np.concatenate(chunks)
    rms = float(np.sqrt(np.mean(audio**2)))
    peak = float(np.max(np.abs(audio)))

    freqs, db = compute_spectrum(audio[-min(len(audio), sr // 2) :], sr, n_fft=2048)
    vis_f, vis_db = resample_log_display(freqs, db, 20, min(20000, sr / 2), n_points=512)
    peak_i = int(np.argmax(vis_db))
    peak_hz = vis_f[peak_i]
    peak_db = float(vis_db[peak_i])

    # Band energy
    def band_energy(lo: float, hi: float) -> float:
        m = (freqs >= lo) & (freqs < hi)
        return float(np.mean(db[m])) if np.any(m) else -120.0

    bass = band_energy(20, 250)
    mids = band_energy(250, 2000)
    treble = band_energy(2000, min(20000, sr / 2))

    print(f"Chunks: {len(chunks)}  Samples: {len(audio)}")
    print(f"RMS: {rms:.6f}  Peak amplitude: {peak:.4f}")
    print(f"Spectrum peak: {peak_hz:,.0f} Hz at {peak_db:.1f} dB")
    print(f"Band means (dB): bass={bass:.1f}  mids={mids:.1f}  treble={treble:.1f}")
    print(f"Frequency bins in last frame: {len(freqs)}")

    if rms < args.rms_threshold:
        print(
            f"\nFAIL: RMS {rms:.6f} below threshold {args.rms_threshold} — "
            "signal too quiet or wrong device."
        )
        return 1

    if peak_db < -60:
        print("\nWARN: Spectrum very weak; capture may be silent or heavily ducked.")

    print("\nPASS: Loopback is receiving audio. Live tab should work with this device index.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
