"""Workspace persistence and manager tests."""

from pathlib import Path

import pytest

from aviz.config import LIBRARY_FILE, WORKSPACE_MANIFEST
from aviz.workspace.manager import WorkspaceManager
from aviz.workspace.persistence import create_workspace, open_workspace, save_workspace


def test_create_and_open_workspace(tmp_workspace: Path):
    ws = create_workspace(tmp_workspace, "Test WS")
    assert (tmp_workspace / WORKSPACE_MANIFEST).exists()
    assert (tmp_workspace / LIBRARY_FILE).exists()
    assert len(ws.playlists) == 1
    assert ws.default_playlist_id in ws.playlists

    ws2 = open_workspace(tmp_workspace)
    assert ws2.name == "Test WS"
    assert len(ws2.playlists) == 1


def test_manager_add_files_and_playlist(tmp_workspace: Path, sample_paths: dict[str, Path]):
    mgr = WorkspaceManager()
    mgr.create(tmp_workspace, "Demo")
    paths = [sample_paths["tone_440hz.wav"], sample_paths["melody_arpeggio.wav"]]
    entries = mgr.add_files(paths)
    assert len(entries) == 2
    assert len(mgr.current.files) == 2

    pl = mgr.create_playlist("Set A")
    for e in entries:
        pl.file_ids.append(e.id)
    mgr.save()

    mgr2 = WorkspaceManager()
    mgr2.open(tmp_workspace)
    pl2 = mgr2.current.get_playlist(pl.id)
    assert pl2 is not None
    assert len(pl2.file_ids) == 2


def test_remove_file_from_playlist(tmp_workspace: Path, tone_wav: Path):
    mgr = WorkspaceManager()
    mgr.create(tmp_workspace, "R")
    entries = mgr.add_files([tone_wav])
    fid = entries[0].id
    pl_id = mgr.current.default_playlist_id
    mgr.current.playlists[pl_id].file_ids.append(fid)
    mgr.remove_file(fid)
    assert fid not in mgr.current.files
    assert fid not in mgr.current.playlists[pl_id].file_ids


def test_visual_settings_persist(tmp_workspace: Path):
    ws = create_workspace(tmp_workspace, "V")
    ws.visual.db_min = -70
    ws.visual.colormap = "magma"
    save_workspace(ws)
    ws2 = open_workspace(tmp_workspace)
    assert ws2.visual.db_min == -70
    assert ws2.visual.colormap == "magma"


def test_open_invalid_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        open_workspace(tmp_path / "not_a_workspace")
