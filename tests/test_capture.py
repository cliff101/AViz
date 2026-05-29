"""Loopback capture helpers (no hardware required)."""

from aviz.audio.capture import LoopbackCapture, list_loopback_devices


def test_list_devices_returns_list():
    devices = list_loopback_devices()
    assert isinstance(devices, list)


def test_capture_stop_without_start():
    cap = LoopbackCapture(device_index=0)
    cap.stop()
    assert not cap.running


def test_read_empty_queue():
    cap = LoopbackCapture(device_index=0)
    assert cap.read(timeout=0.001) is None
