"""Runtime platform detection (desktop vs Android)."""

from __future__ import annotations

import os
import sys


def is_android() -> bool:
    return sys.platform == "android" or bool(os.environ.get("ANDROID_ARGUMENT"))


def is_windows() -> bool:
    return sys.platform == "win32" and not is_android()
