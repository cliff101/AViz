"""Load/save workspace JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aviz.config import (
    CACHE_DIR,
    LIBRARY_FILE,
    PLAYLISTS_DIR,
    WORKSPACE_MANIFEST,
)
from aviz.visual_settings import VisualSettings
from aviz.workspace.models import AudioFileEntry, Group, Playlist, WorkspaceData, _new_id, _utc_now


def create_workspace(root: Path, name: str) -> WorkspaceData:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / PLAYLISTS_DIR).mkdir(exist_ok=True)
    (root / CACHE_DIR).mkdir(parents=True, exist_ok=True)

    main_id = _new_id("pl")
    ws = WorkspaceData(
        root_path=root,
        name=name,
        default_playlist_id=main_id,
        playlists={
            main_id: Playlist(id=main_id, name="Main", file_ids=[]),
        },
    )
    save_workspace(ws)
    return ws


def open_workspace(root: Path) -> WorkspaceData:
    root = root.resolve()
    manifest_path = root / WORKSPACE_MANIFEST
    if not manifest_path.exists():
        raise FileNotFoundError(f"Not a workspace: missing {WORKSPACE_MANIFEST}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    library = _load_library(root)
    playlists = _load_playlists(root)

    ws = WorkspaceData(
        root_path=root,
        name=manifest.get("name", root.name),
        version=int(manifest.get("version", 1)),
        created=manifest.get("created", _utc_now()),
        default_playlist_id=manifest.get("default_playlist_id", ""),
        visual=VisualSettings.from_dict(manifest.get("visual")),
        files=library.get("files", {}),
        groups=library.get("groups", {}),
        playlists=playlists,
        last_session=manifest.get("last_session", {}),
    )
    if not ws.default_playlist_id and ws.playlists:
        ws.default_playlist_id = next(iter(ws.playlists))
    return ws


def save_workspace(ws: WorkspaceData) -> None:
    root = ws.root_path
    manifest = {
        "version": ws.version,
        "name": ws.name,
        "created": ws.created,
        "default_playlist_id": ws.default_playlist_id,
        "visual": ws.visual.to_dict(),
        "last_session": ws.last_session,
    }
    (root / WORKSPACE_MANIFEST).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    _save_library(ws)
    _save_playlists(ws)
    ws.dirty = False


def _load_library(root: Path) -> dict[str, Any]:
    path = root / LIBRARY_FILE
    if not path.exists():
        return {"files": {}, "groups": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    files = {f["id"]: AudioFileEntry.from_dict(f) for f in data.get("files", [])}
    groups = {g["id"]: Group.from_dict(g) for g in data.get("groups", [])}
    return {"files": files, "groups": groups}


def _save_library(ws: WorkspaceData) -> None:
    data = {
        "files": [f.to_dict() for f in ws.files.values()],
        "groups": [g.to_dict() for g in ws.groups.values()],
    }
    (ws.root_path / LIBRARY_FILE).write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )


def _load_playlists(root: Path) -> dict[str, Playlist]:
    pl_dir = root / PLAYLISTS_DIR
    playlists: dict[str, Playlist] = {}
    if not pl_dir.exists():
        return playlists
    for f in pl_dir.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            pl = Playlist.from_dict(d)
            playlists[pl.id] = pl
        except (json.JSONDecodeError, KeyError):
            continue
    return playlists


def _save_playlists(ws: WorkspaceData) -> None:
    pl_dir = ws.root_path / PLAYLISTS_DIR
    pl_dir.mkdir(exist_ok=True)
    for pl in ws.playlists.values():
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in pl.name)
        path = pl_dir / f"{safe}_{pl.id[:8]}.json"
        path.write_text(json.dumps(pl.to_dict(), indent=2), encoding="utf-8")
