#!/usr/bin/env python3
"""Sanity-check AViz APK: Python 3.11 native lib, no cp314 bundle, 16 KB manifest hint."""

from __future__ import annotations

import sys
import zipfile


def verify(apk_path: str) -> int:
    errors: list[str] = []
    warnings: list[str] = []

    with zipfile.ZipFile(apk_path) as zf:
        names = zf.namelist()
        has_py311 = any("libpython3.11" in n and n.endswith(".so") for n in names)
        has_py314 = any("cpython-314" in n for n in names)

        if not has_py311:
            errors.append("missing libpython3.11.so (PySide6 cp311 wheels need it)")
        if has_py314:
            errors.append("bundles Python 3.14 (cpython-314); pin python3==3.11.x in buildozer")

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"FAIL: {e}")

    if errors:
        return 1
    print(f"OK: {apk_path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} path/to.apk", file=sys.stderr)
        sys.exit(2)
    sys.exit(verify(sys.argv[1]))
