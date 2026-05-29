#!/usr/bin/env python3
"""Patch buildozer.spec after pyside6-android-deploy generates it."""

from __future__ import annotations

import sys
from pathlib import Path

PERMS = (
    "android.permissions = RECORD_AUDIO,READ_MEDIA_AUDIO,"
    "READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE"
)
REQUIREMENTS_EXTRA = "numpy,scipy,pyqtgraph,android"
EXCLUDE_DIRS = "tests,scripts,.github,.buildozer,deployment,wheels,.venv,.git"
LOG_LEVEL = "log_level = 2"


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
            for req in REQUIREMENTS_EXTRA.split(","):
                if req not in parts:
                    parts.append(req)
            lines[i] = f"requirements = {','.join(parts)}"
            break

    _upsert(lines, "p4a.branch", "develop", section="app")
    _upsert(lines, "source.exclude_dirs", EXCLUDE_DIRS, section="app")
    _upsert(lines, "log_level", "2", section="buildozer")

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
