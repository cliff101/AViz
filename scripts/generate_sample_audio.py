#!/usr/bin/env python3
"""Write synthetic sample WAV files to samples/ for manual testing."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.helpers.sample_audio import SAMPLE_SPECS, generate_all_samples


def main() -> None:
    out = ROOT / "samples"
    paths = generate_all_samples(out)
    print(f"Generated {len(paths)} files in {out}:")
    for p in paths:
        print(f"  - {p.name} ({p.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
