#!/usr/bin/env python3
"""Patch buildozer.spec after pyside6-android-deploy generates it."""

from __future__ import annotations

import sys
from pathlib import Path

# No scipy/pyqtgraph on Android (native SIGSEGV); charts use plot_stub_android.py
REQUIREMENTS_EXTRA = "numpy,android"
# Must match cp311 PySide6/shiboken Android wheels (libpython3.11.so)
PYTHON_VERSION = "3.11.9"
PYTHON_REQUIREMENTS = (
    f"hostpython3=={PYTHON_VERSION}",
    f"python3=={PYTHON_VERSION}",
)
REQUIRED_PERMISSIONS = (
    "RECORD_AUDIO",
    "READ_MEDIA_AUDIO",
    "READ_EXTERNAL_STORAGE",
    "WRITE_EXTERNAL_STORAGE",
)
EXCLUDE_DIRS = "tests,scripts,.github,.buildozer,deployment,wheels,.venv,.git"
# p4a numpy recipe requires ndk-api >= 24 (buildozer: android.minapi)
NDK_MIN_API = "24"
P4A_HOOK = "android/p4a_hook.py"


def _remove_option(lines: list[str], key: str) -> None:
    prefix = f"{key} ="
    lines[:] = [ln for ln in lines if not ln.strip().startswith(prefix)]


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


def _dedupe_option(lines: list[str], key: str) -> None:
    """Keep the first `key =` line and drop later duplicates (invalid in ConfigParser)."""
    prefix = f"{key} ="
    seen = False
    out: list[str] = []
    for line in lines:
        if line.strip().startswith(prefix):
            if seen:
                continue
            seen = True
        out.append(line)
    lines[:] = out


def _ensure_permissions(lines: list[str]) -> None:
    _dedupe_option(lines, "android.permissions")
    found: list[str] = []
    idx: int | None = None
    for i, line in enumerate(lines):
        if line.strip().startswith("android.permissions ="):
            idx = i
            _, _, rhs = line.partition("=")
            found = [p.strip() for p in rhs.split(",") if p.strip()]
            break
    merged: list[str] = []
    for perm in REQUIRED_PERMISSIONS:
        if perm not in merged:
            merged.append(perm)
    for perm in found:
        if perm not in merged:
            merged.append(perm)
    row = f"android.permissions = {','.join(merged)}"
    if idx is not None:
        lines[idx] = row
        return
    for i, line in enumerate(lines):
        if line.strip().startswith("title ="):
            lines.insert(i + 1, row)
            return
    _upsert(lines, "android.permissions", ",".join(merged), section="app")


def patch(spec_path: Path) -> None:
    lines = spec_path.read_text(encoding="utf-8").splitlines()

    _ensure_permissions(lines)

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
    _upsert(lines, "android.minapi", NDK_MIN_API, section="app")
    _upsert(lines, "source.exclude_dirs", EXCLUDE_DIRS, section="app")
    _upsert(lines, "log_level", "2", section="buildozer")
    _upsert(lines, "p4a.hook", P4A_HOOK, section="app")
    # Do not set android.extra_manifest_application_arguments: buildozer 1.5.0
    # double-escapes values and breaks Gradle (see kivy/buildozer#1611). 16 KB
    # pageSizeCompat is injected by android/p4a_hook.py instead.
    _remove_option(lines, "android.extra_manifest_application_arguments")

    _dedupe_option(lines, "android.permissions")
    _dedupe_option(lines, "p4a.hook")

    spec_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "buildozer.spec")
    if not path.exists():
        raise SystemExit(f"Not found: {path}")
    patch(path)
    print(f"Patched {path}")
