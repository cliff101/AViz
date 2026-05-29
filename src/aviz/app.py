"""Application bootstrap."""

from __future__ import annotations

import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox


def _show_fatal(app: QApplication, title: str, detail: str) -> None:
    QMessageBox.critical(None, title, detail[:12000])
    sys.exit(app.exec())


def _run_import_steps(app: QApplication) -> None:
    """Import heavy deps after QApplication exists (required on Android/Qt)."""
    steps: list[tuple[str, str]] = [
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("pyqtgraph", "pyqtgraph"),
    ]

    for label, mod in steps:
        try:
            __import__(mod)
        except Exception as exc:
            raise RuntimeError(
                f"Import failed: {label}\n{traceback.format_exc()}"
            ) from exc

    import pyqtgraph as pg

    pg.setConfigOptions(antialias=False, useOpenGL=False, foreground="d")


def run() -> None:
    try:
        import android_crash as ac

        ac.boot_log("run: before QApplication")
    except ImportError:
        ac = None
    else:
        from aviz.crash_report import install_crash_handlers

        install_crash_handlers()

    app = QApplication(sys.argv)
    app.setApplicationName("AViz")

    if ac:
        ac.boot_log("run: QApplication ok")
        if ac.show_pending_qt():
            sys.exit(app.exec())

    try:
        _run_import_steps(app)
        if ac:
            ac.boot_log("run: imports ok")
        from aviz.ui.main_window import MainWindow

        win = MainWindow()
    except Exception:
        detail = traceback.format_exc()
        if ac:
            ac.write_crash(detail)
            ac.boot_log("run: exception, showing Qt dialog")
        _show_fatal(app, "AViz failed to start", detail)
        return

    if ac:
        ac.boot_log("run: showing MainWindow")
    win.show()
    sys.exit(app.exec())
