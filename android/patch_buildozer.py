#!/usr/bin/env python3
"""Append Android permissions and requirements to buildozer.spec after deploy init."""

from __future__ import annotations

import sys
from pathlib import Path

PERMS = (
    "android.permissions = RECORD_AUDIO,READ_MEDIA_AUDIO,"
    "READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE"
)
REQUIREMENTS_EXTRA = "python3,numpy,scipy,pyqtgraph,android"


def patch(spec_path: Path) -> None:
    text = spec_path.read_text(encoding="utf-8")
    if PERMS.split("=")[0].strip() in text:
        return
    lines = text.splitlines()
    out: list[str] = []
    inserted_perm = False
    for line in lines:
        out.append(line)
        if line.strip().startswith("requirements =") and REQUIREMENTS_EXTRA not in line:
            base = line.split("=", 1)[1].strip()
            out[-1] = f"requirements = {base},{REQUIREMENTS_EXTRA}"
        if line.strip().startswith("p4a.branch ="):
            out[-1] = "p4a.branch = develop"
        if line.strip() == "[app]" and not inserted_perm:
            continue
        if line.strip().startswith("title =") and not inserted_perm:
            out.append(PERMS)
            inserted_perm = True
    if not inserted_perm:
        out.append("")
        out.append(PERMS)
    spec_path.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "buildozer.spec")
    if not path.exists():
        raise SystemExit(f"Not found: {path}")
    patch(path)
    print(f"Patched {path}")
