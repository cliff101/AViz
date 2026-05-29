"""Application bootstrap."""

from __future__ import annotations

import sys

import pyqtgraph as pg
from PySide6.QtWidgets import QApplication

from aviz.ui.main_window import MainWindow

try:
    import android_crash as _android_crash
except ImportError:
    _android_crash = None

from aviz.crash_report import install_crash_handlers, report_fatal


def run() -> None:
    if _android_crash:
        _android_crash.boot_log("aviz.app.run start")
    else:
        install_crash_handlers()
    # Antialias + OpenGL hurt more than they help for fast-updating 2D plots.
    pg.setConfigOptions(antialias=False, useOpenGL=False, foreground="d")
    app = QApplication(sys.argv)
    app.setApplicationName("AViz")
    try:
        win = MainWindow()
    except Exception as exc:
        if _android_crash:
            _android_crash.report_fatal(exc, title="AViz failed to start")
        else:
            report_fatal(exc, title="AViz failed to start")
        sys.exit(1)
    win.show()
    sys.exit(app.exec())
