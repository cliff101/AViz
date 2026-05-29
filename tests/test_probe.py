"""Loopback probe helpers (used by UI auto-detect)."""

from unittest.mock import MagicMock, patch

import numpy as np

from aviz.audio.capture import (
    LoopbackDevice,
    LoopbackProbeResult,
    best_loopback_probe,
)


def test_best_loopback_probe():
    results = [
        LoopbackProbeResult(LoopbackDevice(1, "a", True), 0.0, 0),
        LoopbackProbeResult(LoopbackDevice(2, "b", True), 0.5, 10),
        LoopbackProbeResult(LoopbackDevice(3, "c", True), 0.1, 5),
    ]
    best = best_loopback_probe(results)
    assert best is not None
    assert best.device.index == 2


def test_has_signal():
    r = LoopbackProbeResult(LoopbackDevice(1, "x", True), 0.0001, 5)
    assert not r.has_signal
    r2 = LoopbackProbeResult(LoopbackDevice(1, "x", True), 0.05, 5)
    assert r2.has_signal
