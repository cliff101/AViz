"""
Minimal Android crash reporter — no aviz imports.

Bundled next to main.py in the APK. Uses jnius + filesystem only.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

_CRASH_NAME = "aviz_last_crash.txt"
_BOOT_NAME = "aviz_boot.txt"
_TAG = "AViz"


def is_mobile_runtime() -> bool:
    if hasattr(sys, "getandroidapilevel"):
        return True
    for key in (
        "ANDROID_ARGUMENT",
        "ANDROID_PRIVATE",
        "ANDROID_UNPACK",
        "ANDROID_APP_PATH",
        "P4A_BOOTSTRAP",
    ):
        if os.environ.get(key):
            return True
    return False


def storage_roots() -> list[Path]:
    if not is_mobile_runtime():
        return []
    roots: list[Path] = []
    for key in (
        "ANDROID_PRIVATE",
        "ANDROID_ARGUMENT",
        "ANDROID_UNPACK",
        "ANDROID_APP_PATH",
    ):
        v = os.environ.get(key)
        if v:
            roots.append(Path(v))
    try:
        roots.append(Path(__file__).resolve().parent)
    except Exception:
        pass
    roots.append(Path("/storage/emulated/0/Download"))
    roots.append(Path("/sdcard/Download"))
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        s = str(r)
        if s not in seen:
            seen.add(s)
            out.append(r)
    return out


def boot_log(line: str) -> None:
    if not is_mobile_runtime():
        return
    stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    text = f"{stamp} {line}\n"
    for root in storage_roots():
        try:
            root.mkdir(parents=True, exist_ok=True)
            with (root / _BOOT_NAME).open("a", encoding="utf-8") as f:
                f.write(text)
        except OSError:
            continue
    log_android(f"boot: {line}")


def log_android(message: str) -> None:
    try:
        from jnius import autoclass  # type: ignore[import-untyped]

        Log = autoclass("android.util.Log")
        Log.e(_TAG, message[:4000])
    except Exception:
        pass


def write_crash(text: str) -> list[str]:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    body = f"AViz crash — {stamp}\n\n{text}"
    written: list[str] = []
    for root in storage_roots():
        try:
            root.mkdir(parents=True, exist_ok=True)
            p = root / _CRASH_NAME
            p.write_text(body, encoding="utf-8")
            written.append(str(p))
        except OSError:
            continue
    return written


def _read_file(name: str) -> str | None:
    for root in storage_roots():
        p = root / name
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8")
            except OSError:
                continue
    return None


def _clear_files() -> None:
    for root in storage_roots():
        for name in (_CRASH_NAME, _BOOT_NAME):
            try:
                (root / name).unlink(missing_ok=True)
            except OSError:
                pass


def show_android_alert(title: str, message: str) -> bool:
    try:
        from jnius import autoclass  # type: ignore[import-untyped]

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        if activity is None:
            log_android("PythonActivity.mActivity is null")
            return False

        Builder = autoclass("android.app.AlertDialog$Builder")
        Toast = autoclass("android.widget.Toast")
        done = threading.Event()

        def on_ui() -> None:
            try:
                short = message if len(message) <= 180 else message[:177] + "..."
                Toast.makeText(activity, f"{title}: {short}", Toast.LENGTH_LONG).show()
            except Exception as exc:
                log_android(f"toast failed: {exc}")
            try:
                b = Builder(activity)
                b.setTitle(title)
                b.setMessage(message[:8000])
                b.setCancelable(True)
                b.setPositiveButton("OK", None)
                b.create().show()
            except Exception as exc:
                log_android(f"alert failed: {exc}")
            done.set()

        try:
            from android.runnable import run_on_ui_thread  # type: ignore[import-untyped]

            run_on_ui_thread(on_ui)
        except ImportError:
            on_ui()

        done.wait(timeout=10)
        time.sleep(25)
        return True
    except Exception as exc:
        log_android(f"show_android_alert: {exc}")
        return False


def show_crash_ui(title: str, detail: str, paths: list[str] | None = None) -> None:
    extra = ""
    if paths:
        extra = "\n\nSaved:\n" + "\n".join(paths[:6])
    body = detail + extra
    log_android(body[:3500])
    if is_mobile_runtime():
        if not show_android_alert(title, body):
            # Last resort: block with toast-only loop
            try:
                from jnius import autoclass  # type: ignore[import-untyped]

                Toast = autoclass("android.widget.Toast")
                act = autoclass("org.kivy.android.PythonActivity").mActivity
                for _ in range(3):
                    Toast.makeText(
                        act,
                        (title + ": " + detail[:120]),
                        Toast.LENGTH_LONG,
                    ).show()
                    time.sleep(4)
            except Exception:
                pass
    else:
        print(f"{title}\n{body}", file=sys.stderr)


def report_fatal(exc: BaseException | None = None, *, title: str = "AViz crashed") -> None:
    if exc is not None:
        detail = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
    else:
        detail = traceback.format_exc()
    if not detail.strip():
        detail = f"{title} (no traceback)"
    paths = write_crash(detail)
    show_crash_ui(title, detail, paths)


def read_pending_message() -> tuple[str, str] | None:
    """Return (title, body) for a crash/boot log from the previous run, if any."""
    crash = _read_file(_CRASH_NAME)
    if crash:
        return ("AViz — previous crash", crash)
    boot = _read_file(_BOOT_NAME)
    early = _read_file("aviz_early.txt")
    parts: list[str] = []
    if boot and boot.strip():
        parts.append(boot.strip())
    if early and early.strip():
        parts.append("--- aviz_early.txt ---\n" + early.strip())
    if parts:
        body = "\n\n".join(parts)
        body += "\n\n(No Python traceback — crash likely before Qt UI or during native code.)"
        return ("AViz — last run stopped early", body)
    return None


def show_pending_qt() -> bool:
    """Show last crash using Qt (call after QApplication exists)."""
    pending = read_pending_message()
    if not pending:
        return False
    title, body = pending
    _clear_files()
    try:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(None, title, body[:12000])
        return True
    except Exception as exc:
        log_android(f"show_pending_qt: {exc}")
        show_crash_ui(title, body)
        return True


def show_pending_crash() -> bool:
    pending = read_pending_message()
    if not pending:
        return False
    title, body = pending
    _clear_files()
    show_crash_ui(title, body)
    return True


def install_excepthook() -> None:
    def hook(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        detail = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        write_crash(detail)
        show_crash_ui("AViz — unhandled error", detail)
        time.sleep(2)
        sys.exit(1)

    sys.excepthook = hook


def install_thread_hook() -> None:
    if not hasattr(threading, "excepthook"):
        return

    def hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_value is not None:
            report_fatal(args.exc_value, title="AViz — thread error")

    threading.excepthook = hook  # type: ignore[attr-defined]


def clear_logs() -> None:
    _clear_files()
    for root in storage_roots():
        try:
            (root / "aviz_early.txt").unlink(missing_ok=True)
        except OSError:
            pass


def bootstrap() -> None:
    if not is_mobile_runtime():
        return
    install_excepthook()
    install_thread_hook()
    show_pending_crash()
