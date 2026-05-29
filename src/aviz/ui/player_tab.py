"""File player — heatmap, transport, prev/next, mini spectrum."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from aviz.analysis.fft import compute_spectrum, peak_hold, smooth_temporal
from aviz.analysis.freq_scales import (
    finalize_spectrum_display,
    normalize_freq_scale,
    prepare_spectrum_display,
)
from aviz.analysis.spectrogram import SpectrogramResult, compute_spectrogram
from aviz.audio.decoder import load_audio_file
from aviz.audio.player import AudioPlayer
from aviz.ui.list_reorder import enable_internal_drag_reorder, file_ids_from_list
from aviz.ui.widgets import SpectrogramPlotWidget, SpectrumPlotWidget
from aviz.ui.widgets.visual_fx_panel import VisualFxPanel
from aviz.visual_settings import VisualSettings
from aviz.workspace.manager import WorkspaceManager

# Match Live: chart refresh ~30 Hz; transport can stay in sync without heavy work.
_VIZ_INTERVAL_MS = 33
_VIZ_HZ = 1000.0 / _VIZ_INTERVAL_MS
_TRANSPORT_INTERVAL_MS = 33

_LOOP_MODES = ("off", "one", "all")
_LOOP_LABELS = ("Loop: Off", "Loop: Track", "Loop: Playlist")


class _AnalyzeWorker(QThread):
    finished = Signal(int, object)
    error = Signal(int, str)

    def __init__(self, load_id: int, path: Path, n_fft: int, hop: int) -> None:
        super().__init__()
        self._load_id = load_id
        self._path = path
        self._n_fft = n_fft
        self._hop = hop

    def run(self) -> None:
        try:
            if self.isInterruptionRequested():
                return
            audio = load_audio_file(self._path)
            if self.isInterruptionRequested():
                return
            mono = (
                audio.samples
                if audio.samples.ndim == 1
                else audio.samples.mean(axis=1)
            )
            if self.isInterruptionRequested():
                return
            spec = compute_spectrogram(mono, audio.sample_rate, self._n_fft, self._hop)
            if self.isInterruptionRequested():
                return
            self.finished.emit(self._load_id, (audio, spec, mono))
        except Exception as e:
            if not self.isInterruptionRequested():
                self.error.emit(self._load_id, str(e))


class PlayerTab(QWidget):
    _playback_finished = Signal()

    def __init__(self, workspace_mgr: WorkspaceManager, parent=None) -> None:
        super().__init__(parent)
        self._mgr = workspace_mgr
        self._settings = VisualSettings()
        self._queue: list[str] = []
        self._queue_index = 0
        self._playlist_id: str | None = None
        self._player = AudioPlayer()
        self._playback_finished.connect(
            self._on_track_finished, Qt.ConnectionType.QueuedConnection
        )
        self._player.on_finished = self._playback_finished.emit
        self._current_spec: SpectrogramResult | None = None
        self._mono: np.ndarray | None = None
        self._worker: _AnalyzeWorker | None = None
        self._load_id = 0
        self._tab_active = False
        self._smooth_state: np.ndarray | None = None
        self._freq_smooth_state: np.ndarray | None = None
        self._peak_state: np.ndarray | None = None
        self._ring_buf: np.ndarray | None = None
        self._ring_write = 0
        self._loop_mode = "off"
        self._shuffle = False
        self._shuffle_order: list[int] = []
        self._play_when_ready = False
        self._block_track_list = False

        layout = QHBoxLayout(self)

        main = QVBoxLayout()
        self._header = QLabel("Open a workspace and select a playlist in Home.")
        self._header.setObjectName("muted")
        self._header.setWordWrap(True)
        main.addWidget(self._header)

        heat_hdr = QHBoxLayout()
        heat_lbl = QLabel("Frequency / time")
        heat_lbl.setObjectName("muted")
        heat_hdr.addWidget(heat_lbl)
        self._center_mode = QCheckBox("Center mode")
        self._center_mode.setToolTip(
            "Keep the playhead (current time) centered in the time axis while playing"
        )
        self._center_mode.toggled.connect(self._on_center_mode)
        heat_hdr.addWidget(self._center_mode)
        heat_hdr.addStretch()
        main.addLayout(heat_hdr)

        self._heatmap = SpectrogramPlotWidget()
        self._heatmap.set_wheel_axis_pick(True)
        self._heatmap.playhead_clicked.connect(self._seek)
        main.addWidget(self._heatmap, stretch=3)

        self._mini = SpectrumPlotWidget()
        self._mini.set_wheel_axis_pick(True)
        self._mini.setMaximumHeight(160)
        main.addWidget(self._mini)

        transport = QHBoxLayout()
        self._btn_prev = QPushButton("⏮ Prev")
        self._btn_play = QPushButton("▶ Play")
        self._btn_next = QPushButton("Next ⏭")
        self._btn_prev.clicked.connect(self._prev_track)
        self._btn_play.clicked.connect(self._toggle_play)
        self._btn_next.clicked.connect(self._next_track)
        transport.addWidget(self._btn_prev)
        transport.addWidget(self._btn_play)
        transport.addWidget(self._btn_next)

        self._loop = QComboBox()
        for label in _LOOP_LABELS:
            self._loop.addItem(label)
        self._loop.setToolTip("Loop current track or entire playlist")
        self._loop.currentIndexChanged.connect(self._on_loop_changed)
        transport.addWidget(self._loop)

        self._shuffle_btn = QCheckBox("Shuffle")
        self._shuffle_btn.setToolTip("Random track order")
        self._shuffle_btn.toggled.connect(self._on_shuffle_changed)
        transport.addWidget(self._shuffle_btn)

        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 1000)
        self._seek_slider.sliderReleased.connect(self._on_seek_slider)
        transport.addWidget(self._seek_slider, stretch=1)

        self._time_label = QLabel("00:00 / 00:00")
        transport.addWidget(self._time_label)
        main.addLayout(transport)

        self._progress = QLabel("")
        self._progress.setObjectName("muted")
        main.addWidget(self._progress)

        layout.addLayout(main, stretch=3)

        pl_panel = QVBoxLayout()
        pl_panel.addWidget(QLabel("Playlist"))
        self._pl_combo = QComboBox()
        self._pl_combo.setToolTip("Active playlist")
        self._pl_combo.currentIndexChanged.connect(self._on_playlist_combo)
        pl_panel.addWidget(self._pl_combo)
        self._track_status = QLabel("—")
        self._track_status.setObjectName("muted")
        self._track_status.setWordWrap(True)
        pl_panel.addWidget(self._track_status)
        self._track_list = QListWidget()
        self._track_list.setToolTip("Drag to reorder · double-click to play")
        enable_internal_drag_reorder(self._track_list, self._on_track_list_reordered)
        self._track_list.itemDoubleClicked.connect(self._on_track_list_activated)
        pl_panel.addWidget(self._track_list, stretch=1)

        pl_wrap = QWidget()
        pl_wrap.setLayout(pl_panel)
        pl_wrap.setMinimumWidth(200)
        pl_wrap.setMaximumWidth(320)
        layout.addWidget(pl_wrap)

        self._fx = VisualFxPanel()
        self._fx.settings_changed.connect(self._on_fx)
        self._fx.reset_view_requested.connect(self._reset_chart_view)
        layout.addWidget(self._fx, stretch=1)

        self._transport_timer = QTimer(self)
        self._transport_timer.timeout.connect(self._update_transport)
        self._transport_timer.setInterval(_TRANSPORT_INTERVAL_MS)

        self._viz_timer = QTimer(self)
        self._viz_timer.timeout.connect(self._update_chart)
        self._viz_timer.setInterval(_VIZ_INTERVAL_MS)

    def set_visual_settings(self, s: VisualSettings) -> None:
        self._settings = s
        self._fx.set_settings(s)
        self._sync_center_mode_ui()
        self._apply_chart_style(force_axes=True)

    def _sync_center_mode_ui(self) -> None:
        on = self._settings.heatmap_center_mode
        self._center_mode.blockSignals(True)
        self._center_mode.setChecked(on)
        self._center_mode.blockSignals(False)
        self._heatmap.set_center_mode(on)

    def _on_center_mode(self, on: bool) -> None:
        self._settings.heatmap_center_mode = on
        self._heatmap.set_center_mode(on)
        if self._mgr.current:
            self._mgr.current.visual = self._settings
            self._mgr.current.dirty = True
        if self._player.audio:
            self._sync_heatmap_playhead(self._player.position)

    def _sync_heatmap_playhead(self, pos: float) -> None:
        self._heatmap.set_playhead(
            pos, center_follow=self._settings.heatmap_center_mode
        )

    def _reset_chart_view(self) -> None:
        s = self._settings
        self._mini.reset_user_view()
        self._heatmap.reset_user_view()
        self._mini.apply_axis_view(
            s.freq_scale,
            s.freq_min_hz,
            s.freq_max_hz,
            s.db_min,
            s.db_max,
            s.scale_x,
            s.scale_y,
            force=True,
        )
        self._heatmap.apply_axis_view(
            s.heatmap_scale_x, s.heatmap_scale_y, force=True
        )

    def _reset_spectrum_state(self) -> None:
        self._smooth_state = None
        self._freq_smooth_state = None
        self._peak_state = None
        self._ring_buf = None
        self._ring_write = 0
        self._mini.reset_plot_cache()

    def _apply_chart_style(
        self,
        prev: VisualSettings | None = None,
        *,
        force_axes: bool = False,
    ) -> None:
        s = self._settings
        p = prev or s
        mini = self._mini

        mini.showGrid(x=s.show_grid, y=s.show_grid, alpha=0.15)
        mini.set_show_peak(s.peak_hold_enabled)
        mini.set_show_glow(s.glow_enabled, s.glow_threshold_db)
        mini.set_colormap(s.colormap)
        mini.set_spectrum_style(s.spectrum_style)
        mini.update_display_metadata(
            s.freq_scale,
            s.freq_min_hz,
            s.freq_max_hz,
            s.db_min,
            s.db_max,
            s.scale_x,
            s.scale_y,
        )
        self._heatmap.set_colormap(s.colormap)
        self._heatmap.set_db_range(s.db_min, s.db_max, s.gamma)

        scale_changed = p.freq_scale != s.freq_scale
        log_changed = scale_changed
        spec_h_scale = p.scale_x != s.scale_x
        spec_v_scale = p.scale_y != s.scale_y
        heat_h_scale = p.heatmap_scale_x != s.heatmap_scale_x
        heat_v_scale = p.heatmap_scale_y != s.heatmap_scale_y
        db_limits_changed = (p.db_min, p.db_max) != (s.db_min, s.db_max)
        freq_limits_changed = (p.freq_min_hz, p.freq_max_hz) != (
            s.freq_min_hz,
            s.freq_max_hz,
        )

        if db_limits_changed:
            mini.apply_db_axis(s.db_min, s.db_max, s.scale_y)

        if scale_changed:
            mini.reset_user_view()
            mini.apply_axis_view(
                s.freq_scale,
                s.freq_min_hz,
                s.freq_max_hz,
                s.db_min,
                s.db_max,
                s.scale_x,
                s.scale_y,
                force=True,
            )
            return

        if not mini.user_view_active() and mini.frequency_view_corrupt():
            mini.repair_frequency_axis()

        if force_axes:
            mini.apply_axis_view(
                s.freq_scale,
                s.freq_min_hz,
                s.freq_max_hz,
                s.db_min,
                s.db_max,
                s.scale_x,
                s.scale_y,
                force=True,
            )
            self._heatmap.apply_axis_view(
                s.heatmap_scale_x, s.heatmap_scale_y, force=True
            )
            return

        if mini.user_view_active():
            if log_changed:
                mini.set_frequency_scale_mode(s.freq_scale)
            if spec_h_scale:
                mini.apply_horizontal_zoom(s.scale_x, p.scale_x)
            if spec_v_scale and not db_limits_changed:
                mini.apply_vertical_zoom(s.scale_y, p.scale_y)
        elif (
            freq_limits_changed
            or log_changed
            or spec_h_scale
            or (spec_v_scale and not db_limits_changed)
        ):
            mini.apply_axis_view(
                s.freq_scale,
                s.freq_min_hz,
                s.freq_max_hz,
                s.db_min,
                s.db_max,
                s.scale_x,
                s.scale_y,
            )

        heat = self._heatmap
        if heat.user_view_active():
            if heat_h_scale:
                heat.apply_horizontal_zoom(s.heatmap_scale_x, p.heatmap_scale_x)
            if heat_v_scale:
                heat.apply_vertical_zoom(s.heatmap_scale_y, p.heatmap_scale_y)
        elif heat_h_scale or heat_v_scale:
            heat.apply_axis_view(s.heatmap_scale_x, s.heatmap_scale_y, force=False)

    def _on_fx(self, s: VisualSettings) -> None:
        prev = self._settings
        self._settings = s
        if prev.n_fft != s.n_fft:
            self._reset_spectrum_state()
        if prev.preset_id != s.preset_id:
            self._reset_spectrum_state()
            self._mini.reset_user_view()
            self._heatmap.reset_user_view()
            self._apply_chart_style(prev=prev, force_axes=True)
        else:
            if prev.freq_scale != s.freq_scale:
                self._mini.reset_plot_cache()
            self._apply_chart_style(prev=prev)
        if self._mgr.current:
            self._mgr.current.visual = s
            self._mgr.current.dirty = True

    def set_playlist(self, playlist_id: str | None) -> None:
        self._playlist_id = playlist_id
        self._reload_queue()

    def _apply_session_prefs(self) -> None:
        ws = self._mgr.current
        if not ws:
            return
        sess = ws.last_session or {}
        if self._playlist_id is None and sess.get("playlist_id"):
            self._playlist_id = str(sess["playlist_id"])
        loop = str(sess.get("loop_mode", "off"))
        if loop in _LOOP_MODES:
            self._loop_mode = loop
        self._shuffle = bool(sess.get("shuffle", False))
        self._loop.blockSignals(True)
        self._loop.setCurrentIndex(_LOOP_MODES.index(self._loop_mode))
        self._loop.blockSignals(False)
        self._shuffle_btn.blockSignals(True)
        self._shuffle_btn.setChecked(self._shuffle)
        self._shuffle_btn.blockSignals(False)

    def _session_start_index(self) -> int:
        ws = self._mgr.current
        if not ws:
            return 0
        sess = ws.last_session or {}
        if str(sess.get("playlist_id", "")) != str(self._playlist_id or ""):
            return 0
        return int(sess.get("queue_index", 0))

    def _save_session(self) -> None:
        ws = self._mgr.current
        if not ws:
            return
        ws.last_session = {
            "playlist_id": self._playlist_id or "",
            "queue_index": self._queue_index,
            "loop_mode": self._loop_mode,
            "shuffle": self._shuffle,
        }
        ws.dirty = True
        self._mgr.save()

    def _on_loop_changed(self, index: int) -> None:
        if 0 <= index < len(_LOOP_MODES):
            self._loop_mode = _LOOP_MODES[index]
            self._save_session()

    def _on_shuffle_changed(self, on: bool) -> None:
        self._shuffle = on
        self._shuffle_order = []
        self._save_session()

    def _on_playlist_combo(self, index: int) -> None:
        if index < 0:
            return
        pl_id = self._pl_combo.itemData(index)
        if pl_id and pl_id != self._playlist_id:
            self._playlist_id = pl_id
            self._reload_queue()

    def _reload_queue(self, *, load_track: bool | None = None) -> None:
        if load_track is None:
            load_track = self._tab_active
        ws = self._mgr.current
        if not ws:
            self._queue = []
            self._refresh_playlist_ui()
            return
        self._apply_session_prefs()
        current_fid = (
            self._queue[self._queue_index]
            if self._queue and 0 <= self._queue_index < len(self._queue)
            else None
        )
        start_idx = self._session_start_index() if load_track else 0
        pl_id = self._playlist_id or ws.default_playlist_id
        pl = ws.get_playlist(pl_id) if pl_id else None
        self._playlist_id = pl_id
        self._queue = list(pl.file_ids) if pl else []
        self._shuffle_order = []
        n = len(self._queue)
        if load_track:
            self._queue_index = min(max(0, start_idx), n - 1) if n else 0
        elif current_fid and current_fid in self._queue:
            self._queue_index = self._queue.index(current_fid)
        else:
            self._queue_index = min(max(0, start_idx), n - 1) if n else 0
        self._refresh_playlist_ui()
        if self._queue and load_track:
            self._load_track_at(self._queue_index)

    def _refresh_playlist_ui(self) -> None:
        ws = self._mgr.current
        self._pl_combo.blockSignals(True)
        self._pl_combo.clear()
        if ws:
            for pl in ws.playlists.values():
                self._pl_combo.addItem(pl.name, pl.id)
            if self._playlist_id:
                i = self._pl_combo.findData(self._playlist_id)
                if i >= 0:
                    self._pl_combo.setCurrentIndex(i)
        self._pl_combo.blockSignals(False)
        self._update_header()
        self._block_track_list = True
        self._track_list.clear()
        if ws and self._queue:
            for i, fid in enumerate(self._queue):
                f = ws.get_file(fid)
                label = f.display_name if f else "?"
                if f and not label:
                    label = Path(f.path).name
                item = QListWidgetItem(f"{i + 1}. {label}")
                item.setData(256, fid)
                self._track_list.addItem(item)
            self._track_list.setCurrentRow(self._queue_index)
        self._block_track_list = False

    def _update_header(self) -> None:
        ws = self._mgr.current
        if not ws or not self._queue:
            self._header.setText("No tracks in playlist — add files in Home.")
            self._track_status.setText("No tracks")
            return
        pl = ws.get_playlist(self._playlist_id or "")
        pl_name = pl.name if pl else "Playlist"
        f = ws.get_file(self._queue[self._queue_index])
        name = f.display_name if f else "?"
        if f and not name:
            name = Path(f.path).name
        n = len(self._queue)
        cur = self._queue_index + 1
        self._header.setText(f"{ws.name}  ›  {pl_name}  ›  {name}")
        self._track_status.setText(f"Playing {cur} of {n}\n{name}")

    def _on_track_list_reordered(self) -> None:
        if self._block_track_list or not self._playlist_id:
            return
        current_fid = (
            self._queue[self._queue_index]
            if self._queue and 0 <= self._queue_index < len(self._queue)
            else None
        )
        new_ids = file_ids_from_list(self._track_list)
        self._mgr.set_playlist_order(self._playlist_id, new_ids)
        self._queue = new_ids
        if current_fid and current_fid in self._queue:
            self._queue_index = self._queue.index(current_fid)
        self._shuffle_order = []
        self._block_track_list = True
        for i in range(self._track_list.count()):
            item = self._track_list.item(i)
            if not item:
                continue
            text = item.text()
            if ". " in text:
                item.setText(f"{i + 1}. {text.split('. ', 1)[1]}")
            else:
                item.setText(f"{i + 1}. {text}")
        self._track_list.setCurrentRow(self._queue_index)
        self._block_track_list = False
        self._update_header()
        self._save_session()

    def _on_track_list_activated(self, item: QListWidgetItem) -> None:
        row = self._track_list.row(item)
        if row < 0 or row >= len(self._queue):
            return
        self._play_when_ready = True
        self._load_track_at(row)

    def _rebuild_shuffle_order(self) -> None:
        n = len(self._queue)
        if n == 0:
            self._shuffle_order = []
            return
        order = list(range(n))
        random.shuffle(order)
        if n > 1 and order[0] == self._queue_index:
            order[0], order[1] = order[1], order[0]
        self._shuffle_order = order

    def _shuffle_position(self) -> int:
        if not self._shuffle_order or len(self._shuffle_order) != len(self._queue):
            self._rebuild_shuffle_order()
        try:
            return self._shuffle_order.index(self._queue_index)
        except ValueError:
            self._rebuild_shuffle_order()
            return 0

    def _next_index(self) -> int | None:
        n = len(self._queue)
        if n == 0:
            return None
        if self._shuffle:
            pos = self._shuffle_position()
            if pos < n - 1:
                return self._shuffle_order[pos + 1]
            if self._loop_mode == "all":
                self._rebuild_shuffle_order()
                return self._shuffle_order[0]
            return None
        if self._queue_index < n - 1:
            return self._queue_index + 1
        if self._loop_mode == "all":
            return 0
        return None

    def _prev_index(self) -> int | None:
        if not self._queue:
            return None
        if self._shuffle:
            pos = self._shuffle_position()
            if pos > 0:
                return self._shuffle_order[pos - 1]
            if self._loop_mode == "all":
                return self._shuffle_order[-1]
            return None
        if self._queue_index > 0:
            return self._queue_index - 1
        if self._loop_mode == "all":
            return len(self._queue) - 1
        return None

    def _abandon_worker(self) -> None:
        """Drop worker callbacks without QThread.terminate() (deadlocks on Windows)."""
        worker = self._worker
        if worker is None:
            return
        try:
            worker.finished.disconnect(self._on_analyzed)
        except (RuntimeError, TypeError):
            pass
        try:
            worker.error.disconnect(self._on_analyze_error)
        except (RuntimeError, TypeError):
            pass
        if worker.isRunning():
            worker.requestInterruption()

    def _load_track_at(self, index: int) -> None:
        ws = self._mgr.current
        if not ws or not self._queue or index < 0 or index >= len(self._queue):
            return
        self._queue_index = index
        fid = self._queue[index]
        entry = ws.get_file(fid)
        if not entry:
            return
        self._player.stop()
        self._stop_timers()
        self._mono = None
        self._reset_spectrum_state()
        self._refresh_playlist_ui()
        self._progress.setText("Analyzing…")
        path = Path(entry.path)
        s = self._settings
        self._abandon_worker()
        self._load_id += 1
        load_id = self._load_id
        self._worker = _AnalyzeWorker(load_id, path, s.n_fft, 512)
        self._worker.finished.connect(self._on_analyzed)
        self._worker.error.connect(self._on_analyze_error)
        self._worker.start()

    def _on_analyzed(self, load_id: int, result: object) -> None:
        if load_id != self._load_id:
            return
        audio, spec, mono = result
        self._current_spec = spec
        self._mono = mono.astype(np.float32, copy=False)
        self._reset_spectrum_state()
        self._heatmap.set_spectrogram(spec)
        self._apply_chart_style(force_axes=True)
        self._player.load_audio(audio)
        self._progress.setText(
            f"{audio.sample_rate} Hz · {audio.channels} ch · {audio.duration:.1f}s · {audio.subtype}"
        )
        self._seek_slider.setRange(0, max(1, int(audio.duration * 1000)))
        self._sync_heatmap_playhead(0.0)
        self._refresh_playlist_ui()
        self._save_session()
        if self._play_when_ready:
            self._play_when_ready = False
            self._player.play()
            self._btn_play.setText("❚❚ Pause")
        if self._tab_active:
            self._start_timers()

    def _on_analyze_error(self, load_id: int, msg: str) -> None:
        if load_id != self._load_id:
            return
        QMessageBox.warning(self, "Load error", msg)
        self._progress.setText(f"Error: {msg}")

    def _start_timers(self) -> None:
        if self._player.audio:
            self._transport_timer.start()
            self._viz_timer.start()

    def _stop_timers(self) -> None:
        self._transport_timer.stop()
        self._viz_timer.stop()

    def on_tab_activated(self) -> None:
        self._tab_active = True
        if self._mgr.is_open and self._queue and self._mono is None:
            running = self._worker is not None and self._worker.isRunning()
            if not running:
                self._load_track_at(self._queue_index)
        self._start_timers()

    def on_tab_deactivated(self) -> None:
        self._tab_active = False
        self._stop_timers()
        if self._player.is_playing:
            self._player.pause()
            self._btn_play.setText("▶ Play")

    def _toggle_play(self) -> None:
        if not self._player.audio:
            return
        self._player.toggle()
        self._btn_play.setText("❚❚ Pause" if self._player.is_playing else "▶ Play")

    def _prev_track(self) -> None:
        if self._player.position > 3.0 and self._player.audio:
            self._player.seek(0)
            return
        prev_i = self._prev_index()
        if prev_i is not None:
            self._play_when_ready = self._player.is_playing
            self._load_track_at(prev_i)
        else:
            self._player.seek(0)

    def _next_track(self) -> None:
        nxt = self._next_index()
        if nxt is not None:
            self._play_when_ready = self._player.is_playing
            self._load_track_at(nxt)

    def _on_track_finished(self) -> None:
        self._player.finalize_on_main_thread()
        if self._loop_mode == "one":
            self._player.seek(0)
            self._player.play()
            self._btn_play.setText("❚❚ Pause")
            return
        nxt = self._next_index()
        if nxt is not None:
            self._play_when_ready = True
            self._load_track_at(nxt)
        else:
            self._btn_play.setText("▶ Play")

    def _seek(self, seconds: float) -> None:
        self._player.seek(seconds)
        self._sync_heatmap_playhead(self._player.position)

    def _on_seek_slider(self) -> None:
        ms = self._seek_slider.value()
        self._player.seek(ms / 1000.0)
        self._sync_heatmap_playhead(self._player.position)

    def _update_transport(self) -> None:
        if not self._player.audio:
            return
        pos = self._player.position
        dur = self._player.duration
        self._sync_heatmap_playhead(pos)
        if not self._seek_slider.isSliderDown():
            self._seek_slider.setValue(int(pos * 1000))
        self._time_label.setText(f"{_fmt(pos)} / {_fmt(dur)}")

    def _update_chart(self) -> None:
        if not self._settings.show_mini_spectrum or self._mono is None:
            return
        audio = self._player.audio
        if not audio:
            return
        self._update_mini_spectrum(self._player.position, audio.sample_rate)

    def _fft_window_at(self, pos: float, sr: int) -> np.ndarray | None:
        mono = self._mono
        if mono is None:
            return None
        n_fft = self._settings.n_fft
        center = int(pos * sr)
        center = int(np.clip(center, 0, len(mono) - 1))
        if self._ring_buf is None or len(self._ring_buf) != n_fft:
            self._ring_buf = np.zeros(n_fft, dtype=np.float32)
            self._ring_write = 0
        start = max(0, center - n_fft + 1)
        chunk = mono[start : center + 1]
        if len(chunk) < 64:
            return None
        n = len(chunk)
        if n >= n_fft:
            return chunk[-n_fft:].astype(np.float32, copy=False)
        self._ring_buf.fill(0)
        self._ring_buf[-n:] = chunk
        return self._ring_buf

    def _update_mini_spectrum(self, pos: float, sr: int) -> None:
        fft_samples = self._fft_window_at(pos, sr)
        if fft_samples is None:
            return
        s = self._settings
        freqs, db = compute_spectrum(fft_samples, sr, n_fft=s.n_fft)

        alpha_t = max(0.05, 1.0 - s.smoothing_time)
        db, self._smooth_state = smooth_temporal(db, alpha_t, self._smooth_state)

        decay = (s.db_max - s.db_min) / max(s.peak_hold_decay_sec * _VIZ_HZ, 1)
        focus_scale = normalize_freq_scale(s.freq_scale) == "focus"
        if s.peak_hold_enabled and not focus_scale:
            self._peak_state = peak_hold(db, self._peak_state, decay)
        elif not s.peak_hold_enabled:
            self._peak_state = None

        x_disp, d_disp, p_disp, hz_disp = prepare_spectrum_display(
            freqs,
            db,
            sr,
            s.freq_scale,
            s.freq_min_hz,
            s.freq_max_hz,
            floor_db=s.db_min,
            peaks=None if focus_scale else self._peak_state,
        )

        x_disp, d_disp, hz_disp, p_disp, self._freq_smooth_state = finalize_spectrum_display(
            x_disp,
            d_disp,
            hz_disp,
            p_disp,
            scale=s.freq_scale,
            smoothing_freq=s.smoothing_freq,
            smooth_state=self._freq_smooth_state,
            floor_db=s.db_min,
        )

        if s.peak_hold_enabled and focus_scale:
            self._peak_state = peak_hold(d_disp, self._peak_state, decay)
            p_disp = self._peak_state

        self._mini.update_spectrum(x_disp, d_disp, p_disp, hz=hz_disp)

    def refresh(self, *, load_track: bool | None = None) -> None:
        if self._mgr.is_open:
            self._reload_queue(load_track=load_track)
            if self._mgr.current:
                self.set_visual_settings(self._mgr.current.visual)
        else:
            self._header.setText("Workspace required — open one from Home.")
            self._queue = []
            self._refresh_playlist_ui()

    def shutdown(self) -> None:
        self._stop_timers()
        self._player.stop()
        self._abandon_worker()
        self._load_id += 1
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            worker.wait(5000)


def _fmt(seconds: float) -> str:
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"
