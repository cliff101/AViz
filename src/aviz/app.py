"""Application bootstrap."""

from __future__ import annotations

import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from aviz.runtime import is_android


def _show_fatal(app: QApplication, title: str, detail: str) -> None:
    QMessageBox.critical(None, title, detail[:12000])
    sys.exit(app.exec())


def _run_desktop() -> None:
    import pyqtgraph as pg

    from aviz.ui.main_window import MainWindow

    pg.setConfigOptions(antialias=False, useOpenGL=False, foreground="d")
    app = QApplication(sys.argv)
    app.setApplicationName("AViz")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


def _run_android() -> None:
    try:
        import android_crash as ac
    except ImportError:
        ac = None

    if ac:
        from aviz.crash_report import install_crash_handlers

        install_crash_handlers()
        ac.boot_log("run: before QApplication")

    app = QApplication(sys.argv)
    app.setApplicationName("AViz")

    if ac:
        ac.boot_log("run: QApplication ok")
        if ac.show_pending_qt():
            sys.exit(app.exec())

    steps = [
        ("numpy", lambda: __import__("numpy")),
        ("pyqtgraph", lambda: __import__("pyqtgraph")),
        ("aviz.ui.main_window", lambda: __import__("aviz.ui.main_window")),
    ]

    for name, fn in steps:
        if ac:
            ac.boot_log(f"run: import {name}")
        try:
            fn()
        except Exception:
            detail = traceback.format_exc()
            if ac:
                ac.write_crash(detail)
            _show_fatal(app, f"AViz import failed: {name}", detail)
            return

    import pyqtgraph as pg

    pg.setConfigOptions(antialias=False, useOpenGL=False, foreground="d")

    if ac:
        ac.boot_log("run: create MainWindow")
    try:
        from aviz.ui.main_window import MainWindow

        win = MainWindow()
    except Exception:
        detail = traceback.format_exc()
        if ac:
            ac.write_crash(detail)
        _show_fatal(app, "AViz failed to start", detail)
        return

    if ac:
        ac.boot_log("run: MainWindow ok")
        ac.clear_logs()
    win.show()
    sys.exit(app.exec())


def run() -> None:
    if is_android():
        _run_android()
    else:
        _run_desktop()
