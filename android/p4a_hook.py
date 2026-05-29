"""python-for-android hook: 16 KB page-size compat on <application>."""

from __future__ import annotations

import re
from pathlib import Path

PAGE_SIZE_ATTR = 'android:pageSizeCompat="enabled"'


def after_apk_build(toolchain) -> None:
    manifest = Path(toolchain._dist.dist_dir) / "src" / "main" / "AndroidManifest.xml"
    if not manifest.is_file():
        print(f"p4a_hook: no manifest at {manifest}")
        return

    text = manifest.read_text(encoding="utf-8")
    if PAGE_SIZE_ATTR in text or "pageSizeCompat" in text:
        print("p4a_hook: pageSizeCompat already in AndroidManifest.xml")
        return

    new_text, count = re.subn(
        r"(<application\b[^>]*)(>)",
        rf"\1 {PAGE_SIZE_ATTR}\2",
        text,
        count=1,
    )
    if count != 1:
        print("p4a_hook: could not patch <application> tag")
        return

    manifest.write_text(new_text, encoding="utf-8")
    print("p4a_hook: injected pageSizeCompat into AndroidManifest.xml")
