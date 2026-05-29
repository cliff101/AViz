"""Live audio capture — WASAPI loopback (Windows) or microphone (Android)."""

from __future__ import annotations

from aviz.runtime import is_android

if is_android():
    from aviz.audio.capture_android import (  # noqa: F401
        LoopbackCapture,
        LoopbackDevice,
        LoopbackProbeResult,
        best_loopback_probe,
        get_default_loopback_device,
        list_loopback_devices,
        probe_loopback_devices,
    )
else:
    from aviz.audio.capture_win import (  # noqa: F401
        LoopbackCapture,
        LoopbackDevice,
        LoopbackProbeResult,
        best_loopback_probe,
        get_default_loopback_device,
        list_loopback_devices,
        probe_loopback_devices,
    )
