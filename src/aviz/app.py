"""Application bootstrap."""

from __future__ import annotations

import sys

import pyqtgraph as pg
from PySide6.QtWidgets import QApplication

from aviz.ui.main_window import MainWindow


def run() -> None:
    # Antialias + OpenGL hurt more than they help for fast-updating 2D plots.
    pg.setConfigOptions(antialias=False, useOpenGL=False, foreground="d")
    app = QApplication(sys.argv)
    app.setApplicationName("AViz")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
