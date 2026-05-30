"""python-for-android hook: compile SDK 35 + 16 KB pageSizeCompat before Gradle."""

from __future__ import annotations

import os
import re
from pathlib import Path

COMPILE_SDK = 35
PAGE_SIZE_ATTR = 'android:pageSizeCompat="enabled"'


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


def _patch_compile_sdk(dist: Path) -> None:
    gradle = dist / "build.gradle"
    if not gradle.is_file():
        print(f"p4a_hook: no build.gradle at {gradle}")
        return

    text = gradle.read_text(encoding="utf-8")
    text = re.sub(
        r"compileSdkVersion\s+\d+",
        f"compileSdkVersion {COMPILE_SDK}",
        text,
        count=1,
    )
    text = re.sub(
        r"compileSdk\s+\d+",
        f"compileSdk {COMPILE_SDK}",
        text,
        count=1,
    )
    text = re.sub(
        r"targetSdkVersion\s+\d+",
        f"targetSdkVersion {COMPILE_SDK}",
        text,
        count=1,
    )
    text = re.sub(
        r"targetSdk\s+\d+",
        f"targetSdk {COMPILE_SDK}",
        text,
        count=1,
    )
    gradle.write_text(text, encoding="utf-8")
    match = re.search(r"compileSdk(?:Version)?\s+(\d+)", text)
    level = match.group(1) if match else "?"
    print(f"p4a_hook: build.gradle compileSdk={level}")


def _patch_manifest(dist: Path) -> None:
    manifest = dist / "src" / "main" / "AndroidManifest.xml"
    if not manifest.is_file():
        print(f"p4a_hook: no manifest at {manifest}")
        return

    text = manifest.read_text(encoding="utf-8")
    text = re.sub(
        r'\s*android:pageSizeCompat=(?:\\"enabled\\"|"enabled")\s*',
        " ",
        text,
    )

    if PAGE_SIZE_ATTR not in text:
        new_text, count = re.subn(
            r"(<application\b[^>]*)(>)",
            rf"\1 {PAGE_SIZE_ATTR}\2",
            text,
            count=1,
        )
        if count != 1:
            print("p4a_hook: could not patch <application> tag")
            return
        text = new_text
        print("p4a_hook: injected pageSizeCompat into AndroidManifest.xml")
    else:
        print("p4a_hook: pageSizeCompat already in AndroidManifest.xml")

    manifest.write_text(text, encoding="utf-8")


def _prepare_dist(toolchain) -> None:
    dist = _dist_dir(toolchain)
    _patch_local_properties(dist)
    _patch_compile_sdk(dist)
    _patch_manifest(dist)


def after_apk_build(toolchain) -> None:
    _prepare_dist(toolchain)


def before_apk_assemble(toolchain) -> None:
    # Re-apply right before gradlew (p4a may regenerate files after after_apk_build).
    _prepare_dist(toolchain)
