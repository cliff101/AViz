"""Show crash details on screen (especially on Android without adb)."""

from __future__ import annotations

import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

from aviz.runtime import is_android


def format_exception(exc: BaseException | None = None) -> str:
    if exc is None:
        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_type is None:
            return "Unknown error (no active exception)"
        lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        return "".join(lines)
    if exc.__traceback__ is not None:
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return f"{type(exc).__name__}: {exc}"


def _crash_log_path() -> Path | None:
    try:
        from aviz.config import CONFIG_DIR

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        return Path(CONFIG_DIR) / "last_crash.txt"
    except Exception:
        return None


def write_crash_log(text: str) -> str | None:
    path = _crash_log_path()
    if path is None:
        return None
    try:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        path.write_text(f"AViz crash — {stamp}\n\n{text}", encoding="utf-8")
        return str(path)
    except OSError:
        return None


def show_crash_dialog(title: str, detail: str, log_path: str | None = None) -> None:
    body = detail
    if log_path:
        body += f"\n\n(Saved to {log_path})"

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication,
            QDialog,
            QDialogButtonBox,
            QLabel,
            QPushButton,
            QTextEdit,
            QVBoxLayout,
        )
    except Exception:
        print(f"{title}\n{body}", file=sys.stderr)
        return

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1] or ["aviz"])

    dlg = QDialog()
    dlg.setWindowTitle(title)
    dlg.setMinimumSize(360, 320)
    layout = QVBoxLayout(dlg)

    hint = QLabel("AViz crashed. Copy this text or read last_crash.txt in app storage.")
    hint.setWordWrap(True)
    layout.addWidget(hint)

    text = QTextEdit()
    text.setReadOnly(True)
    text.setPlainText(body)
    text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
    font = text.font()
    font.setFamily("monospace")
    text.setFont(font)
    layout.addWidget(text)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
    buttons.accepted.connect(dlg.accept)
    layout.addWidget(buttons)

    if is_android():
        copy_btn = QPushButton("Select all")
        copy_btn.clicked.connect(text.selectAll)
        layout.addWidget(copy_btn)

    dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
    dlg.exec()


def report_fatal(exc: BaseException | None = None, *, title: str = "AViz crashed") -> None:
    detail = format_exception(exc)
    log_path = write_crash_log(detail)
    if is_android() or bool(sys.environ.get("AVIZ_SHOW_CRASH_UI")):
        show_crash_dialog(title, detail, log_path)
    else:
        print(f"{title}\n{detail}", file=sys.stderr)
        if log_path:
            print(f"Log: {log_path}", file=sys.stderr)


def _excepthook(exc_type: type[BaseException], exc_value: BaseException, exc_tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    detail = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log_path = write_crash_log(detail)
    if is_android() or bool(sys.environ.get("AVIZ_SHOW_CRASH_UI")):
        show_crash_dialog("AViz — unhandled error", detail, log_path)
        sys.exit(1)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
    if args.exc_value is not None:
        report_fatal(args.exc_value, title="AViz — thread error")


def install_crash_handlers() -> None:
    sys.excepthook = _excepthook
    if hasattr(threading, "excepthook"):
        threading.excepthook = _thread_excepthook
