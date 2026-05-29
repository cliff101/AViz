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

    try:
        if ac:
            ac.boot_log("run: import numpy")
        __import__("numpy")
        if ac:
            ac.boot_log("run: import aviz.ui.main_window")
        from aviz.ui.main_window import MainWindow

        if ac:
            ac.boot_log("run: create MainWindow")
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
