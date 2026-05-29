#!/usr/bin/env python3
"""Patch buildozer.spec after pyside6-android-deploy generates it."""

from __future__ import annotations

import sys
from pathlib import Path

PERMS = (
    "android.permissions = RECORD_AUDIO,READ_MEDIA_AUDIO,"
    "READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE"
)
# No scipy/pyqtgraph on Android (native SIGSEGV); charts use plot_stub_android.py
REQUIREMENTS_EXTRA = "numpy,android"
# Must match cp311 PySide6/shiboken Android wheels (libpython3.11.so)
PYTHON_VERSION = "3.11.9"
PYTHON_REQUIREMENTS = (
    f"hostpython3=={PYTHON_VERSION}",
    f"python3=={PYTHON_VERSION}",
)
EXCLUDE_DIRS = "tests,scripts,.github,.buildozer,deployment,wheels,.venv,.git"
LOG_LEVEL = "log_level = 2"
P4A_HOOK = "p4a.hook = android/p4a_hook.py"
# Samsung / Android 15+ devices with 16 KB pages: Qt .so from PySide6 wheels need compat mode
MANIFEST_APP_ARGS = (
    "android.extra_manifest_application_arguments = "
    "android/extra_manifest_application_arguments.xml"
)


def _pin_python311(parts: list[str]) -> list[str]:
    parts = [
        p
        for p in parts
        if not p.lower().startswith(("python3", "hostpython3"))
    ]
    return list(PYTHON_REQUIREMENTS) + parts


def _upsert(lines: list[str], key: str, value: str, section: str | None = None) -> None:
    prefix = f"{key} ="
    for i, line in enumerate(lines):
        if line.strip().startswith(prefix):
            lines[i] = f"{key} = {value}"
            return
    if section:
        for i, line in enumerate(lines):
            if line.strip() == f"[{section}]":
                lines.insert(i + 1, f"{key} = {value}")
                return
    lines.append(f"{key} = {value}")


def patch(spec_path: Path) -> None:
    lines = spec_path.read_text(encoding="utf-8").splitlines()

    if not any("android.permissions = RECORD_AUDIO" in ln for ln in lines):
        for i, line in enumerate(lines):
            if line.strip().startswith("title ="):
                lines.insert(i + 1, PERMS)
                break

    for i, line in enumerate(lines):
        if line.strip().startswith("requirements ="):
            base = line.split("=", 1)[1].strip()
            parts = [p.strip() for p in base.split(",") if p.strip()]
            parts = [
                p
                for p in parts
                if p.lower() not in ("scipy", "pyqtgraph", "matplotlib")
            ]
            parts = _pin_python311(parts)
            for req in REQUIREMENTS_EXTRA.split(","):
                if req not in parts:
                    parts.append(req)
            lines[i] = f"requirements = {','.join(parts)}"
            break

    _upsert(lines, "p4a.branch", "develop", section="app")
    _upsert(lines, "source.exclude_dirs", EXCLUDE_DIRS, section="app")
    _upsert(lines, "log_level", "2", section="buildozer")
    if "p4a.hook" not in "\n".join(lines):
        lines.append(P4A_HOOK)
    if "extra_manifest_application_arguments" not in "\n".join(lines):
        lines.append(MANIFEST_APP_ARGS)

    text = "\n".join(lines) + "\n"
    if "android.permissions = RECORD_AUDIO" not in text:
        text = PERMS + "\n" + text
    spec_path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "buildozer.spec")
    if not path.exists():
        raise SystemExit(f"Not found: {path}")
    patch(path)
    print(f"Patched {path}")
