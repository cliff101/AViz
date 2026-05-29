#!/usr/bin/env python3
"""Start AViz — opens the main window.

    python main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running without pip install -e (uses src/ package)
_ROOT = Path(__file__).resolve().parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

if __name__ == "__main__":
    from aviz.crash_report import boot_main

    boot_main()
