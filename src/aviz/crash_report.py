"""Show crash details on screen (especially on Android without adb)."""

from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from aviz.runtime import is_android

_CRASH_BASENAME = "last_crash.txt"
_BOOT_BASENAME = "boot_log.txt"


def format_exception(exc: BaseException | None = None) -> str:
    if exc is None:
        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_type is None:
            return "Unknown error (no active exception)"
        return "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    if exc.__traceback__ is not None:
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return f"{type(exc).__name__}: {exc}"


def should_show_crash_ui() -> bool:
    if os.environ.get("AVIZ_NO_CRASH_UI"):
        return False
    if os.environ.get("AVIZ_SHOW_CRASH_UI"):
        return True
    return is_android()


def _crash_dirs() -> list[Path]:
    dirs: list[Path] = []
    try:
        from aviz.config import CONFIG_DIR

        dirs.append(Path(CONFIG_DIR))
    except Exception:
        pass
    private = os.environ.get("ANDROID_PRIVATE")
    if private:
        dirs.append(Path(private))
    if hasattr(sys, "getandroidapilevel"):
        try:
            from jnius import autoclass  # type: ignore[import-untyped]

            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            ctx = activity.getApplicationContext()
            for getter in ("getFilesDir", "getExternalFilesDir"):
                try:
                    d = getattr(ctx, getter)()
                    if d is not None:
                        dirs.append(Path(d.getAbsolutePath()))
                except Exception:
                    pass
        except Exception:
            pass
    dirs.append(Path.cwd())
    seen: set[str] = set()
    out: list[Path] = []
    for d in dirs:
        key = str(d)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def _crash_file(name: str) -> Path | None:
    for d in _crash_dirs():
        try:
            d.mkdir(parents=True, exist_ok=True)
            return d / name
        except OSError:
            continue
    return None


def boot_log(message: str) -> None:
    if not should_show_crash_ui():
        return
    path = _crash_file(_BOOT_BASENAME)
    if path is None:
        return
    try:
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{stamp} {message}\n")
    except OSError:
        pass


def write_crash_log(text: str) -> str | None:
    boot_tail = ""
    boot_path = _crash_file(_BOOT_BASENAME)
    if boot_path and boot_path.is_file():
        try:
            boot_tail = "\n\n--- boot log ---\n" + boot_path.read_text(encoding="utf-8")[-4000:]
        except OSError:
            pass
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    body = f"AViz crash — {stamp}\n\n{text}{boot_tail}"
    written: list[str] = []
    for d in _crash_dirs():
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / _CRASH_BASENAME
            p.write_text(body, encoding="utf-8")
            written.append(str(p))
        except OSError:
            continue
    return written[0] if written else None


def _read_pending_crash() -> str | None:
    for d in _crash_dirs():
        p = d / _CRASH_BASENAME
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8")
            except OSError:
                continue
    return None


def _clear_pending_crash() -> None:
    for d in _crash_dirs():
        try:
            (d / _CRASH_BASENAME).unlink(missing_ok=True)
            (d / _BOOT_BASENAME).unlink(missing_ok=True)
        except OSError:
            pass


def show_pending_crash() -> bool:
    text = _read_pending_crash()
    if text:
        _clear_pending_crash()
        show_crash_ui("AViz — previous crash", text, log_path=None)
        return True
    boot_path = _crash_file(_BOOT_BASENAME)
    if boot_path and boot_path.is_file():
        try:
            boot = boot_path.read_text(encoding="utf-8").strip()
        except OSError:
            boot = ""
        if boot:
            _clear_pending_crash()
            show_crash_ui(
                "AViz — last run stopped early (no Python traceback)",
                boot + "\n\nIf this repeats, the crash may be in Qt/native code.",
                log_path=None,
            )
            return True
    return False


def _show_android_native_alert(title: str, message: str) -> bool:
    try:
        from jnius import autoclass  # type: ignore[import-untyped]

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        Builder = autoclass("android.app.AlertDialog$Builder")
        Toast = autoclass("android.widget.Toast")
        shown = threading.Event()

        def on_ui_thread() -> None:
            try:
                short = message if len(message) <= 200 else message[:197] + "..."
                Toast.makeText(
                    activity,
                    f"{title}: {short}",
                    Toast.LENGTH_LONG,
                ).show()
            except Exception:
                pass
            try:
                builder = Builder(activity)
                builder.setTitle(title)
                builder.setMessage(message[:6000])
                builder.setCancelable(True)
                builder.setPositiveButton("OK", None)
                dialog = builder.create()
                dialog.show()
            except Exception:
                pass
            shown.set()

        try:
            from android.runnable import run_on_ui_thread  # type: ignore[import-untyped]

            run_on_ui_thread(on_ui_thread)
        except ImportError:
            on_ui_thread()

        shown.wait(timeout=8)
        time.sleep(20)
        return True
    except Exception:
        return False


def _show_qt_crash_dialog(title: str, body: str) -> bool:
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
        return False

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1] or ["aviz"])

    dlg = QDialog()
    dlg.setWindowTitle(title)
    dlg.setMinimumSize(360, 320)
    layout = QVBoxLayout(dlg)

    hint = QLabel("AViz error (scroll / Select all to copy)")
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

    copy_btn = QPushButton("Select all")
    copy_btn.clicked.connect(text.selectAll)
    layout.addWidget(copy_btn)

    dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    app.processEvents()
    dlg.exec()
    return True


def show_crash_ui(title: str, detail: str, log_path: str | None = None) -> None:
    body = detail
    if log_path:
        body += f"\n\n(Saved to {log_path})"

    if is_android() and _show_android_native_alert(title, body):
        return
    if _show_qt_crash_dialog(title, body):
        return
    print(f"{title}\n{body}", file=sys.stderr)


def report_fatal(exc: BaseException | None = None, *, title: str = "AViz crashed") -> None:
    detail = format_exception(exc)
    log_path = write_crash_log(detail)
    if should_show_crash_ui():
        show_crash_ui(title, detail, log_path)
    else:
        print(f"{title}\n{detail}", file=sys.stderr)
        if log_path:
            print(f"Log: {log_path}", file=sys.stderr)


def _excepthook(exc_type: type[BaseException], exc_value: BaseException, exc_tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    detail = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    write_crash_log(detail)
    if should_show_crash_ui():
        show_crash_ui("AViz — unhandled error", detail)
        sys.exit(1)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
    if args.exc_value is not None:
        report_fatal(args.exc_value, title="AViz — thread error")


def install_crash_handlers() -> None:
    sys.excepthook = _excepthook
    if hasattr(threading, "excepthook"):
        threading.excepthook = _thread_excepthook


def boot_main() -> None:
    """Legacy entry — main.py uses android_crash.bootstrap() at repo root."""
    install_crash_handlers()
    show_pending_crash()
    from aviz.app import run

    run()
