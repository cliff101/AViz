#!/usr/bin/env python3
"""Start AViz — opens the main window.

    python main.py
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _early_log(msg: str) -> None:
    """Stdlib-only trace (runs before any project import)."""
    line = f"{msg}\n"
    bases: list[str] = []
    for key in ("ANDROID_PRIVATE", "ANDROID_ARGUMENT", "ANDROID_UNPACK"):
        v = os.environ.get(key)
        if v:
            bases.append(v)
    bases.extend(("/storage/emulated/0/Download", "/sdcard/Download", "."))
    for base in bases:
        try:
            with open(os.path.join(base, "aviz_early.txt"), "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass


_early_log("main.py: start")

_ROOT = Path(__file__).resolve().parent
for _p in (_ROOT / "src", _ROOT):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

_early_log("main.py: sys.path ready")

_ac = None
try:
    import android_crash as _ac

    _ac.boot_log("main.py: android_crash ok")
    _ac.bootstrap()
except Exception as exc:
    _early_log(f"main.py: android_crash failed: {exc!r}")

try:
    _early_log("main.py: import aviz.app")
    from aviz.app import run

    _early_log("main.py: calling run()")
    run()
    _early_log("main.py: run() returned")
except SystemExit:
    raise
except BaseException as exc:
    _early_log(f"main.py: exception {exc!r}")
    detail = traceback.format_exc()
    if _ac:
        _ac.write_crash(detail)
        _ac.report_fatal(exc, title="AViz failed")
        import time

        time.sleep(30)
    raise SystemExit(1) from exc
