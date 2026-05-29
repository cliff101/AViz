"""Runtime platform detection (desktop vs Android)."""

from __future__ import annotations

import os
import sys


def is_android() -> bool:
    """True when running inside the packaged Android app (p4a / PySide deploy)."""
    if sys.platform == "android":
        return True
    if hasattr(sys, "getandroidapilevel"):
        return True
    if os.environ.get("ANDROID_ARGUMENT") or os.environ.get("ANDROID_PRIVATE"):
        return True
    try:
        from jnius import autoclass  # type: ignore[import-untyped]

        autoclass("org.kivy.android.PythonActivity")
        return True
    except Exception:
        return False


def is_windows() -> bool:
    return sys.platform == "win32" and not is_android()
