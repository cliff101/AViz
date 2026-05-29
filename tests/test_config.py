"""App config helpers."""

from pathlib import Path

from aviz.config import load_recent_workspaces, save_recent_workspaces


def test_recent_workspaces_roundtrip(tmp_path, monkeypatch):
    cfg_file = tmp_path / "recent.json"
    monkeypatch.setattr("aviz.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("aviz.config.RECENT_WORKSPACES_FILE", cfg_file)

    save_recent_workspaces([r"C:\ws1", r"C:\ws2"])
    loaded = load_recent_workspaces()
    assert loaded[0] == r"C:\ws1"
    assert len(loaded) == 2
