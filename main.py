#!/usr/bin/env python3
"""Start AViz — opens the main window.

    python main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# --- Android crash bootstrap (no aviz imports) ---
try:
    import android_crash as _ac

    _ac.boot_log("main.py module load")
    _ac.bootstrap()
except Exception:
    _ac = None  # type: ignore[assignment]

_ROOT = Path(__file__).resolve().parent
for _p in (_ROOT / "src", _ROOT):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

if _ac:
    _ac.boot_log("sys.path ready")


def _fatal(exc: BaseException, title: str) -> None:
    if _ac:
        _ac.report_fatal(exc, title=title)
        import time

        time.sleep(30)
    else:
        raise exc


# p4a runs this file via PyRun_SimpleFile (__name__ == "__main__").
# Do not guard startup — always run when executed.
try:
    if _ac:
        _ac.boot_log("import aviz.app")
    from aviz.app import run

    if _ac:
        _ac.boot_log("calling run()")
    run()
    if _ac:
        _ac.boot_log("run() returned")
except SystemExit:
    raise
except BaseException as exc:
    _fatal(exc, "AViz failed")
    raise SystemExit(1) from exc
