#!/usr/bin/env python3
"""Try every loopback device briefly; report which receives audio."""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np

from aviz.audio.capture import LoopbackCapture, list_loopback_devices


def probe(index: int, seconds: float = 2.0) -> tuple[float, int]:
    cap = LoopbackCapture(device_index=index)
    cap.start()
    time.sleep(0.2)
    chunks = []
    deadline = time.time() + seconds
    while time.time() < deadline:
        c = cap.read(timeout=0.15)
        if c is not None and len(c):
            chunks.append(c)
    cap.stop()
    if not chunks:
        return 0.0, 0
    audio = np.concatenate(chunks)
    return float(np.sqrt(np.mean(audio**2))), len(chunks)


def main() -> int:
    devices = list_loopback_devices()
    if not devices:
        print("No loopback devices")
        return 1
    print("Probing each device (keep music playing)…\n")
    best = (0.0, None, 0)
    for d in devices:
        rms, n = probe(d.index, 2.0)
        status = "OK" if rms > 0.001 and n > 0 else "silent"
        print(f"  [{d.index:2d}] RMS={rms:.6f} chunks={n:3d}  {status}  {d.name}")
        if rms > best[0]:
            best = (rms, d, n)

    if best[1] is None or best[0] < 0.0005:
        print("\nNo device received audio. Play music on speakers/Bluetooth and retry.")
        return 1
    print(f"\nBest device: [{best[1].index}] {best[1].name}")
    print(f"Use in app or: python scripts/test_loopback_live.py --device-index {best[1].index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
