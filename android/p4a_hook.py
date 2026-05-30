"""python-for-android hook: point Gradle at the PySide SDK; strip pageSizeCompat."""

from __future__ import annotations

import os
import re
from pathlib import Path

# PySide's android-35 platform jar does not expose pageSizeCompat to AAPT even when
# compileSdk is 35. Injecting it breaks Gradle. Users enable 16 KB compat in Settings.


def _dist_dir(toolchain) -> Path:
    return Path(toolchain._dist.dist_dir)


def _patch_local_properties(dist: Path) -> None:
    sdk = os.environ.get("ANDROIDSDK") or os.environ.get("ANDROID_SDK")
    if not sdk:
        print("p4a_hook: ANDROIDSDK not set, skipping local.properties")
        return
    sdk_dir = sdk.replace("\\", "/")
    props = dist / "local.properties"
    props.write_text(f"sdk.dir={sdk_dir}\n", encoding="utf-8")
    print(f"p4a_hook: sdk.dir={sdk_dir}")


def _strip_page_size_compat(dist: Path) -> None:
    manifest = dist / "src" / "main" / "AndroidManifest.xml"
    if not manifest.is_file():
        return
    text = manifest.read_text(encoding="utf-8")
    new_text = re.sub(
        r'\s*android:pageSizeCompat=(?:\\"enabled\\"|"disabled\\"|"enabled"|"disabled")\s*',
        " ",
        text,
    )
    if new_text != text:
        manifest.write_text(new_text, encoding="utf-8")
        print("p4a_hook: removed pageSizeCompat from AndroidManifest.xml")
    else:
        print("p4a_hook: no pageSizeCompat in AndroidManifest.xml")


def _prepare_dist(toolchain) -> None:
    dist = _dist_dir(toolchain)
    _patch_local_properties(dist)
    _strip_page_size_compat(dist)


def after_apk_build(toolchain) -> None:
    _prepare_dist(toolchain)


def before_apk_assemble(toolchain) -> None:
    _prepare_dist(toolchain)
