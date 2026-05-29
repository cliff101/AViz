"""Application-wide configuration."""

from __future__ import annotations

import json
from pathlib import Path

from aviz.runtime import is_android

APP_NAME = "AViz"


def _default_config_dir() -> Path:
    if is_android():
        try:
            from jnius import autoclass  # type: ignore[import-untyped]

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            context = PythonActivity.mActivity.getApplicationContext()
            files_dir = context.getFilesDir().getAbsolutePath()
            return Path(files_dir) / "aviz"
        except Exception:
            pass
    return Path.home() / ".aviz"


CONFIG_DIR = _default_config_dir()
RECENT_WORKSPACES_FILE = CONFIG_DIR / "recent_workspaces.json"
MAX_RECENT = 8

DEFAULT_SAMPLE_RATE = 48000
DEFAULT_BLOCK_SIZE = 512
DEFAULT_HOP = 512
DEFAULT_N_FFT = 2048

WORKSPACE_MANIFEST = "aviz.workspace.json"
LIBRARY_FILE = "library.json"
PLAYLISTS_DIR = "playlists"
CACHE_DIR = "cache/spectrograms"

AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".wma", ".aiff", ".aif"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".m4v"}


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_recent_workspaces() -> list[str]:
    ensure_config_dir()
    if not RECENT_WORKSPACES_FILE.exists():
        return []
    try:
        data = json.loads(RECENT_WORKSPACES_FILE.read_text(encoding="utf-8"))
        return list(data.get("paths", []))[:MAX_RECENT]
    except (json.JSONDecodeError, OSError):
        return []


def save_recent_workspaces(paths: list[str]) -> None:
    ensure_config_dir()
    RECENT_WORKSPACES_FILE.write_text(
        json.dumps({"paths": paths[:MAX_RECENT]}, indent=2),
        encoding="utf-8",
    )
