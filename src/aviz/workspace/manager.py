"""Workspace lifecycle and library mutations."""

from __future__ import annotations

from pathlib import Path

from aviz.config import load_recent_workspaces, save_recent_workspaces
from aviz.workspace.models import AudioFileEntry, Group, Playlist, WorkspaceData, _new_id, _utc_now
from aviz.workspace.persistence import create_workspace, open_workspace, save_workspace


class WorkspaceManager:
    def __init__(self) -> None:
        self.current: WorkspaceData | None = None

    @property
    def is_open(self) -> bool:
        return self.current is not None

    def create(self, root: Path, name: str) -> WorkspaceData:
        self.current = create_workspace(root, name)
        self._touch_recent()
        return self.current

    def open(self, root: Path) -> WorkspaceData:
        self.current = open_workspace(root)
        self._touch_recent()
        return self.current

    def close(self) -> None:
        if self.current and self.current.dirty:
            save_workspace(self.current)
        self.current = None

    def save(self) -> None:
        if self.current:
            save_workspace(self.current)

    def add_files(self, paths: list[Path]) -> list[AudioFileEntry]:
        if not self.current:
            raise RuntimeError("No workspace open")
        added = []
        for p in paths:
            p = Path(p).resolve()
            if not p.exists():
                continue
            existing = next(
                (f for f in self.current.files.values() if Path(f.path) == p),
                None,
            )
            if existing:
                added.append(existing)
                continue
            entry = AudioFileEntry.from_path(p)
            self.current.files[entry.id] = entry
            added.append(entry)
        self.current.dirty = True
        self.save()
        return added

    def remove_file(self, file_id: str) -> None:
        if not self.current:
            return
        self.current.files.pop(file_id, None)
        for g in self.current.groups.values():
            g.file_ids = [i for i in g.file_ids if i != file_id]
        for pl in self.current.playlists.values():
            pl.file_ids = [i for i in pl.file_ids if i != file_id]
        self.current.dirty = True
        self.save()

    def create_group(self, name: str) -> Group:
        if not self.current:
            raise RuntimeError("No workspace open")
        g = Group(id=_new_id("g"), name=name)
        self.current.groups[g.id] = g
        self.current.dirty = True
        self.save()
        return g

    def create_playlist(self, name: str) -> Playlist:
        if not self.current:
            raise RuntimeError("No workspace open")
        pl = Playlist(id=_new_id("pl"), name=name)
        self.current.playlists[pl.id] = pl
        if not self.current.default_playlist_id:
            self.current.default_playlist_id = pl.id
        self.current.dirty = True
        self.save()
        return pl

    def set_playlist_order(self, playlist_id: str, file_ids: list[str]) -> None:
        if not self.current:
            return
        pl = self.current.get_playlist(playlist_id)
        if not pl:
            return
        pl.file_ids = list(file_ids)
        self.current.dirty = True
        self.save()

    def remove_playlist(self, playlist_id: str) -> None:
        if not self.current:
            return
        if playlist_id not in self.current.playlists:
            return
        self.current.playlists.pop(playlist_id, None)
        if self.current.default_playlist_id == playlist_id:
            remaining = list(self.current.playlists.keys())
            self.current.default_playlist_id = remaining[0] if remaining else ""
        self.current.dirty = True
        self.save()

    def update_file_metadata(self, entry: AudioFileEntry) -> None:
        if not self.current:
            return
        self.current.files[entry.id] = entry
        self.current.dirty = True
        self.save()

    def _touch_recent(self) -> None:
        if not self.current:
            return
        path = str(self.current.root_path)
        recent = [p for p in load_recent_workspaces() if p != path]
        recent.insert(0, path)
        save_recent_workspaces(recent)
