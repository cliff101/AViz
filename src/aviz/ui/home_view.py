"""Home — workspace, library, groups, playlists."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from aviz.config import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, load_recent_workspaces
from aviz.ui.list_reorder import enable_internal_drag_reorder, file_ids_from_list
from aviz.ui.theme import TEXT_MUTED
from aviz.workspace.manager import WorkspaceManager


class HomeView(QWidget):
    workspace_changed = Signal()
    open_player = Signal()
    go_live = Signal()

    def __init__(self, workspace_mgr: WorkspaceManager, parent=None) -> None:
        super().__init__(parent)
        self._mgr = workspace_mgr

        root = QVBoxLayout(self)
        title = QLabel("Home")
        title.setObjectName("title")
        root.addWidget(title)

        guide = QLabel(
            "File library & playlists (Player tab). For real-time speaker visualization, "
            "use the Live tab — no workspace required."
        )
        guide.setWordWrap(True)
        guide.setObjectName("muted")
        root.addWidget(guide)

        quick = QHBoxLayout()
        go_live = QPushButton("Open Live monitor")
        go_live.setObjectName("accent")
        go_live.clicked.connect(self._go_live)
        quick.addWidget(go_live)
        quick.addStretch()
        root.addLayout(quick)

        self._status = QLabel("No workspace open — create or open one for file mode.")
        self._status.setObjectName("muted")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        btn_row = QHBoxLayout()
        self._btn_create = QPushButton("Create workspace…")
        self._btn_open = QPushButton("Open workspace…")
        self._btn_close = QPushButton("Close workspace")
        self._btn_create.clicked.connect(self._create_workspace)
        self._btn_open.clicked.connect(self._open_workspace)
        self._btn_close.clicked.connect(self._close_workspace)
        btn_row.addWidget(self._btn_create)
        btn_row.addWidget(self._btn_open)
        btn_row.addWidget(self._btn_close)
        root.addLayout(btn_row)

        self._recent = QListWidget()
        self._recent.itemDoubleClicked.connect(self._open_recent)
        root.addWidget(QLabel("Recent workspaces"))
        root.addWidget(self._recent)

        splitter = QSplitter()
        lib_panel = QWidget()
        lib_layout = QVBoxLayout(lib_panel)
        lib_lbl = QLabel("Library")
        lib_lbl.setToolTip("Ctrl+click: toggle · Shift+click: range · Remove / Add work on all selected")
        lib_layout.addWidget(lib_lbl)
        self._library = QListWidget()
        self._library.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._library.itemDoubleClicked.connect(lambda: self.open_player.emit())
        lib_layout.addWidget(self._library)
        lib_btns = QHBoxLayout()
        add_btn = QPushButton("Add files…")
        add_btn.clicked.connect(self._add_files)
        rem_btn = QPushButton("Remove")
        rem_btn.clicked.connect(self._remove_file)
        lib_btns.addWidget(add_btn)
        lib_btns.addWidget(rem_btn)
        lib_layout.addLayout(lib_btns)
        splitter.addWidget(lib_panel)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Playlists"))
        self._playlists = QListWidget()
        self._playlists.currentRowChanged.connect(self._on_playlist_select)
        right_layout.addWidget(self._playlists)
        pl_btns = QHBoxLayout()
        new_pl = QPushButton("New playlist")
        new_pl.clicked.connect(self._new_playlist)
        del_pl = QPushButton("Delete playlist")
        del_pl.clicked.connect(self._delete_playlist)
        add_to_pl = QPushButton("Add selected to playlist")
        add_to_pl.clicked.connect(self._add_to_playlist)
        pl_btns.addWidget(new_pl)
        pl_btns.addWidget(del_pl)
        pl_btns.addWidget(add_to_pl)
        right_layout.addLayout(pl_btns)
        self._playlist_files = QListWidget()
        self._playlist_files.setToolTip("Drag tracks to reorder the playlist")
        enable_internal_drag_reorder(
            self._playlist_files, self._on_playlist_tracks_reordered
        )
        self._block_pl_reorder = False
        right_layout.addWidget(QLabel("Tracks in playlist"))
        right_layout.addWidget(self._playlist_files)
        open_pl = QPushButton("Open in Player")
        open_pl.setObjectName("accent")
        open_pl.clicked.connect(self.open_player.emit)
        right_layout.addWidget(open_pl)
        splitter.addWidget(right)
        splitter.setSizes([400, 400])
        root.addWidget(splitter, stretch=1)

        self.refresh()

    def refresh(self) -> None:
        self._recent.clear()
        for p in load_recent_workspaces():
            self._recent.addItem(p)

        ws = self._mgr.current
        if ws:
            self._status.setText(
                f"Workspace: {ws.name}\n{ws.root_path}\n"
                f"{len(ws.files)} files · {len(ws.playlists)} playlists"
            )
            self._btn_close.setEnabled(True)
        else:
            self._status.setText(
                "No workspace open — create or open one for file mode."
            )
            self._btn_close.setEnabled(False)

        self._library.clear()
        self._playlists.clear()
        self._playlist_files.clear()
        if not ws:
            return
        for f in ws.files.values():
            item = QListWidgetItem(
                f"{f.display_name or Path(f.path).name}  ({f.duration_sec:.1f}s)"
            )
            item.setData(256, f.id)
            self._library.addItem(item)
        for pl in ws.playlists.values():
            item = QListWidgetItem(pl.name)
            item.setData(256, pl.id)
            self._playlists.addItem(item)
        if ws.default_playlist_id:
            for i in range(self._playlists.count()):
                if self._playlists.item(i).data(256) == ws.default_playlist_id:
                    self._playlists.setCurrentRow(i)
                    break

    def _create_workspace(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Create workspace in folder")
        if not folder:
            return
        name, ok = QInputDialog.getText(self, "Workspace name", "Name:", text=Path(folder).name)
        if not ok or not name.strip():
            return
        try:
            self._mgr.create(Path(folder), name.strip())
            self.refresh()
            self.workspace_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _open_workspace(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open workspace folder")
        if not folder:
            return
        try:
            self._mgr.open(Path(folder))
            self.refresh()
            self.workspace_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _open_recent(self, item: QListWidgetItem) -> None:
        try:
            self._mgr.open(Path(item.text()))
            self.refresh()
            self.workspace_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _close_workspace(self) -> None:
        self._mgr.close()
        self.refresh()
        self.workspace_changed.emit()

    def _add_files(self) -> None:
        if not self._mgr.is_open:
            QMessageBox.warning(self, "Workspace", "Open a workspace first.")
            return
        exts = " ".join(f"*{e}" for e in sorted(AUDIO_EXTENSIONS | VIDEO_EXTENSIONS))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add audio/video", "", f"Media ({exts});;All (*.*)"
        )
        if not paths:
            return
        from aviz.audio.decoder import load_audio_file

        added = self._mgr.add_files([Path(p) for p in paths])
        for entry in added:
            try:
                audio = load_audio_file(Path(entry.path))
                entry.duration_sec = audio.duration
                entry.sample_rate = audio.sample_rate
                entry.channels = audio.channels
                entry.subtype = audio.subtype
                entry.display_name = audio.display_name
                self._mgr.update_file_metadata(entry)
            except Exception:
                pass
        self.refresh()

    def _selected_library_ids(self) -> list[str]:
        return [item.data(256) for item in self._library.selectedItems()]

    def _remove_file(self) -> None:
        ws = self._mgr.current
        if not ws:
            return
        for fid in self._selected_library_ids():
            self._mgr.remove_file(fid)
        if self._library.selectedItems():
            self.refresh()

    def _new_playlist(self) -> None:
        if not self._mgr.is_open:
            return
        name, ok = QInputDialog.getText(self, "Playlist", "Name:")
        if ok and name.strip():
            self._mgr.create_playlist(name.strip())
            self.refresh()

    def _delete_playlist(self) -> None:
        item = self._playlists.currentItem()
        if not item or not self._mgr.current:
            return
        pl_id = item.data(256)
        pl = self._mgr.current.get_playlist(pl_id)
        if not pl:
            return
        n = len(pl.file_ids)
        msg = f"Delete playlist “{pl.name}”?"
        if n:
            msg += f"\n{n} track reference(s) will be removed from the playlist (files stay in the library)."
        if (
            QMessageBox.question(self, "Delete playlist", msg)
            != QMessageBox.StandardButton.Yes
        ):
            return
        self._mgr.remove_playlist(pl_id)
        self.refresh()
        self.workspace_changed.emit()

    def _on_playlist_select(self) -> None:
        self._fill_playlist_tracks()

    def _fill_playlist_tracks(self) -> None:
        self._block_pl_reorder = True
        self._playlist_files.clear()
        ws = self._mgr.current
        item = self._playlists.currentItem()
        if not ws or not item:
            self._block_pl_reorder = False
            return
        pl = ws.get_playlist(item.data(256))
        if not pl:
            self._block_pl_reorder = False
            return
        for i, fid in enumerate(pl.file_ids):
            f = ws.get_file(fid)
            if not f:
                continue
            label = f.display_name or Path(f.path).name
            row = QListWidgetItem(f"{i + 1}. {label}")
            row.setData(256, fid)
            self._playlist_files.addItem(row)
        self._block_pl_reorder = False

    def _on_playlist_tracks_reordered(self) -> None:
        if self._block_pl_reorder:
            return
        ws = self._mgr.current
        pl_item = self._playlists.currentItem()
        if not ws or not pl_item:
            return
        pl_id = pl_item.data(256)
        new_ids = file_ids_from_list(self._playlist_files)
        self._mgr.set_playlist_order(pl_id, new_ids)
        for i in range(self._playlist_files.count()):
            item = self._playlist_files.item(i)
            if item:
                text = item.text()
                if ". " in text:
                    item.setText(f"{i + 1}. {text.split('. ', 1)[1]}")
                else:
                    item.setText(f"{i + 1}. {text}")
        self.workspace_changed.emit()

    def _add_to_playlist(self) -> None:
        ws = self._mgr.current
        pl_item = self._playlists.currentItem()
        lib_items = self._library.selectedItems()
        if not ws or not pl_item or not lib_items:
            return
        pl = ws.get_playlist(pl_item.data(256))
        if not pl:
            return
        changed = False
        for lib_item in lib_items:
            fid = lib_item.data(256)
            if fid not in pl.file_ids:
                pl.file_ids.append(fid)
                changed = True
        if changed:
            ws.dirty = True
            self._mgr.save()
            self._fill_playlist_tracks()

    def get_selected_playlist_id(self) -> str | None:
        item = self._playlists.currentItem()
        return item.data(256) if item else None

    def _go_live(self) -> None:
        self.go_live.emit()
