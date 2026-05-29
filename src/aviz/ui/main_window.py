"""Main application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

from aviz.config import APP_NAME
from aviz.ui.home_view import HomeView
from aviz.ui.live_tab import LiveTab
from aviz.ui.player_tab import PlayerTab
from aviz.ui.theme import STYLESHEET
from aviz.workspace.manager import WorkspaceManager


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — Audio Visualization")
        self.resize(1280, 800)
        self.setStyleSheet(STYLESHEET)

        self._workspace_mgr = WorkspaceManager()
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        self._home = HomeView(self._workspace_mgr)
        self._live = LiveTab(self._workspace_mgr)
        self._player = PlayerTab(self._workspace_mgr)

        self._tabs.addTab(self._home, "Home")
        self._tabs.addTab(self._live, "Live")
        self._tabs.addTab(self._player, "Player")

        self._home.workspace_changed.connect(self._on_workspace_changed)
        self._home.open_player.connect(self._open_player)
        self._home.go_live.connect(lambda: self._tabs.setCurrentIndex(1))
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._build_menu()

    def _build_menu(self) -> None:
        menu_file = self.menuBar().addMenu("&File")
        act_open = QAction("&Open workspace…", self)
        act_open.triggered.connect(self._home._open_workspace)
        menu_file.addAction(act_open)
        act_create = QAction("&Create workspace…", self)
        act_create.triggered.connect(self._home._create_workspace)
        menu_file.addAction(act_create)
        menu_file.addSeparator()
        act_quit = QAction("E&xit", self)
        act_quit.setShortcut(QKeySequence.Quit)
        act_quit.triggered.connect(self.close)
        menu_file.addAction(act_quit)

        menu_view = self.menuBar().addMenu("&View")
        for i, label in enumerate(("Home", "Live", "Player")):
            act = QAction(f"Go to {label}", self)
            act.triggered.connect(lambda checked=False, idx=i: self._tabs.setCurrentIndex(idx))
            menu_view.addAction(act)

        menu_help = self.menuBar().addMenu("&Help")
        act_start = QAction("&Quick start guide", self)
        act_start.triggered.connect(self._show_quick_start)
        menu_help.addAction(act_start)

    def _show_quick_start(self) -> None:
        root = Path(__file__).resolve().parents[3]
        samples = root / "samples"
        QMessageBox.information(
            self,
            "Quick start",
            "Run the app:  python main.py\n\n"
            "1. Live — play music, Auto-detect, Start listening.\n"
            "2. Home — Create workspace, Add files.\n"
            "3. Player — Open in Player; transport + Visual FX.\n\n"
            f"Sample audio:\n{samples}",
        )

    def _on_workspace_changed(self) -> None:
        # Do not analyze tracks while user is on Home (avoids UI freeze / deadlocks).
        self._player.refresh(load_track=False)
        if self._workspace_mgr.current:
            self._live.set_visual_settings(self._workspace_mgr.current.visual)
            self._player.set_visual_settings(self._workspace_mgr.current.visual)

    def _open_player(self) -> None:
        if not self._workspace_mgr.is_open:
            QMessageBox.information(
                self,
                "Workspace required",
                "Create or open a workspace in Home before using the Player.",
            )
            self._tabs.setCurrentWidget(self._home)
            return
        pl_id = self._home.get_selected_playlist_id()
        self._player.set_playlist(pl_id)
        self._tabs.setCurrentIndex(2)

    def _on_tab_changed(self, index: int) -> None:
        if index != 2:
            self._player.on_tab_deactivated()
        if index == 1:
            self._live.on_tab_activated()
        if index == 2:
            if not self._workspace_mgr.is_open:
                QMessageBox.information(
                    self,
                    "Workspace required",
                    "Create or open a workspace in Home to use the Player.",
                )
                self._tabs.setCurrentIndex(0)
                return
            self._player.on_tab_activated()

    def closeEvent(self, event) -> None:
        self._live.shutdown()
        self._player.shutdown()
        if self._workspace_mgr.current and self._workspace_mgr.current.dirty:
            self._workspace_mgr.save()
        self._workspace_mgr.close()
        super().closeEvent(event)
