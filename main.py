#!/usr/bin/env python3
"""Start AViz — opens the main window.

    python main.py
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))


def _is_android_env() -> bool:
    if hasattr(sys, "getandroidapilevel"):
        return True
    return bool(os.environ.get("ANDROID_ARGUMENT") or os.environ.get("ANDROID_PRIVATE"))


def _android_toast(message: str) -> None:
    try:
        from android.runnable import run_on_ui_thread  # type: ignore[import-untyped]
        from jnius import autoclass  # type: ignore[import-untyped]

        Toast = autoclass("android.widget.Toast")
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        length = Toast.LENGTH_LONG

        def show() -> None:
            Toast.makeText(activity, message, length).show()

        run_on_ui_thread(show)
    except Exception:
        pass


def _android_start() -> None:
    _android_toast("AViz: Python started")
    time.sleep(0.5)
    try:
        import android_crash as ac

        ac.bootstrap()
    except Exception:
        pass
    try:
        from aviz.app import run

        run()
    except BaseException:
        detail = traceback.format_exc()
        try:
            import android_crash as ac

            ac.write_crash(detail)
            ac.report_fatal(title="AViz crashed")
        except Exception:
            _android_toast("AViz crashed (see log)")
        time.sleep(20)
        raise SystemExit(1) from None


def main() -> None:
    if _is_android_env():
        _android_start()
        return
    from aviz.app import run

    run()


if __name__ == "__main__":
    main()
