"""Application bootstrap."""

from __future__ import annotations

import sys

import pyqtgraph as pg
from PySide6.QtWidgets import QApplication

from aviz.crash_report import install_crash_handlers, report_fatal
from aviz.ui.main_window import MainWindow


def run() -> None:
    install_crash_handlers()
    # Antialias + OpenGL hurt more than they help for fast-updating 2D plots.
    pg.setConfigOptions(antialias=False, useOpenGL=False, foreground="d")
    app = QApplication(sys.argv)
    app.setApplicationName("AViz")
    try:
        win = MainWindow()
    except Exception as exc:
        report_fatal(exc, title="AViz failed to start")
        raise
    win.show()
    sys.exit(app.exec())
