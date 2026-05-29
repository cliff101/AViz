#!/usr/bin/env python3
"""Start AViz — opens the main window.

    python main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))


def main() -> None:
    from aviz.runtime import is_android

    if is_android():
        try:
            import android_crash as ac

            ac.bootstrap()
        except Exception:
            pass

    from aviz.app import run

    run()


if __name__ == "__main__":
    main()
