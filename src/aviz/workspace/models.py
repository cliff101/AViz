"""Workspace data models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aviz.visual_settings import VisualSettings


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AudioFileEntry:
    id: str
    path: str
    display_name: str = ""
    duration_sec: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    subtype: str = ""
    added_at: str = field(default_factory=_utc_now)

    @classmethod
    def from_path(cls, path: Path) -> AudioFileEntry:
        return cls(
            id=_new_id("f"),
            path=str(path.resolve()),
            display_name=path.name,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "display_name": self.display_name,
            "duration_sec": self.duration_sec,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "subtype": self.subtype,
            "added_at": self.added_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AudioFileEntry:
        return cls(
            id=d["id"],
            path=d["path"],
            display_name=d.get("display_name", ""),
            duration_sec=float(d.get("duration_sec", 0)),
            sample_rate=int(d.get("sample_rate", 0)),
            channels=int(d.get("channels", 0)),
            subtype=d.get("subtype", ""),
            added_at=d.get("added_at", _utc_now()),
        )


@dataclass
class Group:
    id: str
    name: str
    file_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "file_ids": self.file_ids}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Group:
        return cls(id=d["id"], name=d["name"], file_ids=list(d.get("file_ids", [])))


@dataclass
class Playlist:
    id: str
    name: str
    file_ids: list[str] = field(default_factory=list)
    updated_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "file_ids": self.file_ids,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Playlist:
        return cls(
            id=d["id"],
            name=d["name"],
            file_ids=list(d.get("file_ids", [])),
            updated_at=d.get("updated_at", _utc_now()),
        )


@dataclass
class WorkspaceData:
    root_path: Path
    name: str
    version: int = 1
    created: str = field(default_factory=_utc_now)
    default_playlist_id: str = ""
    visual: VisualSettings = field(default_factory=VisualSettings)
    files: dict[str, AudioFileEntry] = field(default_factory=dict)
    groups: dict[str, Group] = field(default_factory=dict)
    playlists: dict[str, Playlist] = field(default_factory=dict)
    last_session: dict[str, Any] = field(default_factory=dict)
    dirty: bool = False

    def get_file(self, file_id: str) -> AudioFileEntry | None:
        return self.files.get(file_id)

    def get_playlist(self, playlist_id: str) -> Playlist | None:
        return self.playlists.get(playlist_id)
