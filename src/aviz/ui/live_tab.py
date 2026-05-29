"""Live monitor — full spectrum of all frequencies from loopback."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from aviz.analysis.fft import (
    compute_spectrum,
    peak_hold,
    smooth_temporal,
)
from aviz.analysis.freq_scales import (
    finalize_spectrum_display,
    normalize_freq_scale,
    prepare_spectrum_display,
)
from aviz.audio.capture import (
    LoopbackCapture,
    best_loopback_probe,
    get_default_loopback_device,
    list_loopback_devices,
    probe_loopback_devices,
)
from aviz.ui.theme import ACCENT, DANGER, TEXT_MUTED
from aviz.ui.widgets import SpectrumPlotWidget, WaterfallPlotWidget
from aviz.ui.widgets.visual_fx_panel import VisualFxPanel
from aviz.visual_settings import VisualSettings, apply_preset
from aviz.runtime import is_android
from aviz.workspace.manager import WorkspaceManager


class _ProbeWorker(QThread):
    finished = Signal(object)

    def run(self) -> None:
        self.finished.emit(probe_loopback_devices(1.8))


# ~30 Hz spectrum refresh — smooth enough, much cheaper than 60 Hz.
_TIMER_INTERVAL_MS: int = 33
_TIMER_HZ: float = 1000.0 / _TIMER_INTERVAL_MS
_METRICS_INTERVAL: int = 8
_WATERFALL_FRAME_SKIP: int = 2
# How many silent ticks before showing "no signal" (~3 seconds)
_SILENT_TICKS_THRESHOLD: int = round(3000 / _TIMER_INTERVAL_MS)


class LiveTab(QWidget):
    def __init__(
        self, workspace_mgr: WorkspaceManager | None = None, parent=None
    ) -> None:
        super().__init__(parent)
        self._workspace_mgr = workspace_mgr
        self._settings = VisualSettings()
        self._capture: LoopbackCapture | None = None
        self._smooth_state: np.ndarray | None = None
        self._freq_smooth_state: np.ndarray | None = None
        self._peak_state: np.ndarray | None = None
        self._ring_buf: np.ndarray | None = None
        self._silent_ticks = 0
        self._tick_i = 0
        self._listening_status = False
        self._ring_write = 0
        self._probe_worker: _ProbeWorker | None = None

        layout = QHBoxLayout(self)

        center = QVBoxLayout()

        if is_android():
            guide_text = (
                "Live spectrum from the device microphone — grant mic permission, then Start. "
                "Wheel on chart: left = level · center = both · right = frequency."
            )
        else:
            guide_text = (
                "Listen to what your PC is playing: choose the output device, then Start. "
                "Wheel on chart: left = level · center = both · right = frequency. "
                "Shift/Ctrl force one axis. FX sliders also adjust zoom."
            )
        guide = QLabel(guide_text)
        guide.setWordWrap(True)
        guide.setObjectName("muted")
        center.addWidget(guide)

        self._status = QLabel("● Stopped — press Start listening")
        self._status.setStyleSheet(f"color: {TEXT_MUTED}; font-weight: 600;")

        header = QHBoxLayout()
        header.addWidget(QLabel("Input device" if is_android() else "Output device"))
        self._device = QComboBox()
        self._device.setMinimumWidth(280)
        header.addWidget(self._device, stretch=1)

        self._btn_refresh = QPushButton("Refresh")
        self._btn_refresh.clicked.connect(self._refresh_devices)
        header.addWidget(self._btn_refresh)

        self._btn_detect = QPushButton("Auto-detect")
        self._btn_detect.setToolTip("Find the device that receives audio (play music first)")
        self._btn_detect.clicked.connect(self._auto_detect)
        header.addWidget(self._btn_detect)

        self._btn_start = QPushButton("Start listening")
        self._btn_start.setObjectName("accent")
        self._btn_start.clicked.connect(self._start)
        header.addWidget(self._btn_start)

        self._btn_stop = QPushButton("Stop")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop)
        header.addWidget(self._btn_stop)
        center.addLayout(header)
        center.addWidget(self._status)
        self._refresh_devices()

        self._info = QLabel("Full spectrum: every frequency (Hz) vs strength (dB)")
        self._info.setObjectName("muted")
        center.addWidget(self._info)

        self._spectrum = SpectrumPlotWidget()
        self._spectrum.set_wheel_axis_pick(True)
        center.addWidget(self._spectrum, stretch=1)

        self._waterfall = WaterfallPlotWidget()
        self._waterfall.getViewBox().setXLink(self._spectrum.getViewBox())
        self._waterfall.hide()
        center.addWidget(self._waterfall)

        self._metrics = QLabel("Peak: — Hz · RMS: — dB · Bins: —")
        self._metrics.setObjectName("muted")
        center.addWidget(self._metrics)

        layout.addLayout(center, stretch=3)

        self._fx = VisualFxPanel()
        self._fx.settings_changed.connect(self._on_fx)
        self._fx.reset_view_requested.connect(self._reset_chart_view)
        layout.addWidget(self._fx, stretch=1)
        self._fx.set_settings(self._settings)
        self._apply_plot_style(force_axes=True)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(_TIMER_INTERVAL_MS)

    def _reset_chart_view(self) -> None:
        self._spectrum.reset_user_view()
        s = self._settings
        self._spectrum.apply_axis_view(
            s.freq_scale,
            s.freq_min_hz,
            s.freq_max_hz,
            s.db_min,
            s.db_max,
            s.scale_x,
            s.scale_y,
            force=True,
        )

    def on_tab_activated(self) -> None:
        """Refresh device list when user opens the Live tab."""
        self._refresh_devices()
        self._sync_settings_from_workspace()
        self._prepare_spectrum_for_listen(force=False)

    def _sync_settings_from_workspace(self) -> None:
        if self._workspace_mgr and self._workspace_mgr.current:
            self._settings = self._workspace_mgr.current.visual
            self._fx.set_settings(self._settings)

    def _prepare_spectrum_for_listen(self, *, force: bool) -> None:
        s = self._settings
        self._spectrum.reset_plot_cache()
        self._spectrum.ensure_view_coherent(
            s.freq_scale,
            s.freq_min_hz,
            s.freq_max_hz,
            s.db_min,
            s.db_max,
            s.scale_x,
            s.scale_y,
            force=force,
        )
        if s.waterfall_enabled:
            self._sync_waterfall(reset_buffer=True)

    def set_visual_settings(self, s: VisualSettings) -> None:
        self._settings = s
        self._fx.set_settings(s)
        self._prepare_spectrum_for_listen(
            force=not self._spectrum.user_view_active()
        )

    def _on_fx(self, s: VisualSettings) -> None:
        prev = self._settings
        self._settings = s
        if prev.n_fft != s.n_fft:
            self._smooth_state = None
            self._freq_smooth_state = None
            self._peak_state = None
            self._ring_buf = None
        if prev.preset_id != s.preset_id:
            self._smooth_state = None
            self._freq_smooth_state = None
            self._peak_state = None
            self._spectrum.reset_user_view()
            self._apply_plot_style(prev=prev, force_axes=True)
            return
        if prev.waterfall_enabled != s.waterfall_enabled:
            self._waterfall.clear_history()
        if prev.freq_scale != s.freq_scale:
            self._waterfall.clear_history()
            self._spectrum.reset_plot_cache()
        self._apply_plot_style(prev=prev)

    def _set_status(self, text: str, ok: bool | None = None) -> None:
        color = ACCENT if ok is True else (DANGER if ok is False else TEXT_MUTED)
        self._status.setText(text)
        self._status.setStyleSheet(f"color: {color}; font-weight: 600;")

    def _apply_plot_style(
        self,
        prev: VisualSettings | None = None,
        force_axes: bool = False,
    ) -> None:
        s = self._settings
        p = prev or s
        sp = self._spectrum

        sp.showGrid(x=s.show_grid, y=s.show_grid, alpha=0.15)
        sp.set_show_peak(s.peak_hold_enabled)
        sp.set_show_glow(s.glow_enabled, s.glow_threshold_db)
        sp.set_colormap(s.colormap)
        sp.set_spectrum_style(s.spectrum_style)
        self._waterfall.setVisible(s.waterfall_enabled)
        if self._waterfall_needs_configure(p, s, force_axes):
            self._sync_waterfall(
                reset_buffer=force_axes or (p.waterfall_enabled != s.waterfall_enabled)
            )
        sp.update_display_metadata(
            s.freq_scale,
            s.freq_min_hz,
            s.freq_max_hz,
            s.db_min,
            s.db_max,
            s.scale_x,
            s.scale_y,
        )

        scale_changed = p.freq_scale != s.freq_scale
        log_changed = scale_changed
        h_scale_changed = p.scale_x != s.scale_x
        v_scale_changed = p.scale_y != s.scale_y
        db_limits_changed = (p.db_min, p.db_max) != (s.db_min, s.db_max)
        freq_limits_changed = (p.freq_min_hz, p.freq_max_hz) != (
            s.freq_min_hz,
            s.freq_max_hz,
        )
        limits_changed = db_limits_changed or freq_limits_changed

        if db_limits_changed:
            sp.apply_db_axis(s.db_min, s.db_max, s.scale_y)

        if scale_changed:
            sp.reset_user_view()
            sp.apply_axis_view(
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

        if not sp.user_view_active() and sp.frequency_view_corrupt():
            sp.repair_frequency_axis()

        if force_axes:
            sp.apply_axis_view(
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

        if sp.user_view_active():
            # Freq cuts / log mode: data only. dB limits handled above via apply_db_axis.
            if log_changed:
                sp.set_frequency_scale_mode(s.freq_scale)
            if h_scale_changed:
                sp.apply_horizontal_zoom(s.scale_x, p.scale_x)
            if v_scale_changed and not db_limits_changed:
                sp.apply_vertical_zoom(s.scale_y, p.scale_y)
            return

        if (
            freq_limits_changed
            or log_changed
            or h_scale_changed
            or (v_scale_changed and not db_limits_changed)
        ):
            sp.apply_axis_view(
                s.freq_scale,
                s.freq_min_hz,
                s.freq_max_hz,
                s.db_min,
                s.db_max,
                s.scale_x,
                s.scale_y,
            )

    def _waterfall_needs_configure(
        self,
        prev: VisualSettings,
        cur: VisualSettings,
        force_axes: bool,
    ) -> bool:
        if force_axes:
            return True
        return (
            prev.waterfall_enabled != cur.waterfall_enabled
            or prev.colormap != cur.colormap
            or (prev.db_min, prev.db_max, prev.gamma)
            != (cur.db_min, cur.db_max, cur.gamma)
            or prev.freq_scale != cur.freq_scale
            or (prev.freq_min_hz, prev.freq_max_hz)
            != (cur.freq_min_hz, cur.freq_max_hz)
            or prev.scale_x != cur.scale_x
            or prev.waterfall_depth != cur.waterfall_depth
        )

    def _sync_waterfall(self, *, reset_buffer: bool = False) -> None:
        s = self._settings
        self._waterfall.configure(
            colormap=s.colormap,
            db_min=s.db_min,
            db_max=s.db_max,
            gamma=s.gamma,
            depth=s.waterfall_depth,
            freq_scale=s.freq_scale,
            f_min_hz=s.freq_min_hz,
            f_max_hz=s.freq_max_hz,
            scale_x=s.scale_x,
            reset_buffer=reset_buffer,
            x_linked=True,
        )

    def _refresh_devices(self) -> None:
        self._device.clear()
        devs = list_loopback_devices()
        if not devs:
            msg = (
                "No microphone — check permission"
                if is_android()
                else "No loopback — reinstall PyAudioWPatch"
            )
            self._device.addItem(msg, -1)
            self._set_status("● No capture devices — check installation", ok=False)
            return
        default_lb = get_default_loopback_device()
        select_row = 0
        for i, d in enumerate(devs):
            label = d.name
            if default_lb and d.index == default_lb.index:
                label += " (default output)"
                select_row = i
            self._device.addItem(label, d.index)
        self._device.setCurrentIndex(select_row)
        if not self._capture:
            self._set_status("● Ready — press Start listening", ok=None)

    def _select_device_index(self, index: int) -> None:
        for i in range(self._device.count()):
            if self._device.itemData(i) == index:
                self._device.setCurrentIndex(i)
                return

    def _auto_detect(self) -> None:
        if not list_loopback_devices():
            if is_android():
                QMessageBox.warning(
                    self,
                    "No devices",
                    "Microphone capture is unavailable.\n\n"
                    "Grant RECORD_AUDIO in app settings and try again.",
                )
            else:
                QMessageBox.warning(
                    self,
                    "No devices",
                    "No loopback devices found.\n\n"
                    "Install loopback support:\n"
                    "  pip install PyAudioWPatch",
                )
            return
        self._btn_detect.setEnabled(False)
        self._btn_start.setEnabled(False)
        detect_hint = (
            "● Auto-detecting… make sound near the microphone"
            if is_android()
            else "● Auto-detecting… play audio on your speakers now"
        )
        self._set_status(detect_hint, ok=None)

        self._probe_worker = _ProbeWorker()
        self._probe_worker.finished.connect(self._on_probe_done)
        self._probe_worker.start()

    def _on_probe_done(self, results: object) -> None:
        self._btn_detect.setEnabled(True)
        self._btn_start.setEnabled(True)
        from aviz.audio.capture import LoopbackProbeResult

        probes: list[LoopbackProbeResult] = results  # type: ignore[assignment]
        best = best_loopback_probe(probes)

        if best is None or not best.has_signal:
            self._set_status("● No audio detected on any device", ok=False)
            if is_android():
                hint = (
                    "No audio was captured from the microphone.\n\n"
                    "• Grant microphone permission\n"
                    "• Play audio near the device or speak\n"
                    "• Press Start listening to visualize"
                )
            else:
                hint = (
                    "No audio was captured on any output.\n\n"
                    "• Start playing music or video\n"
                    "• Make sure Windows sound is going to speakers/headphones\n"
                    "• Try each device in the list manually, then Start listening"
                )
            QMessageBox.warning(self, "Auto-detect", hint)
            return

        self._select_device_index(best.device.index)
        self._set_status(
            f"● Found signal on: {best.device.name} (RMS {best.rms:.3f})",
            ok=True,
        )
        QMessageBox.information(
            self,
            "Auto-detect",
            f"Active output:\n{best.device.name}\n\n"
            f"Signal level: {best.rms:.3f}\n\n"
            "Press Start listening to visualize.",
        )

    def _start(self) -> None:
        idx = self._device.currentData()
        if idx is None or idx < 0:
            QMessageBox.warning(self, "Device", "Select a valid output device first.")
            return
        self._sync_settings_from_workspace()
        self._prepare_spectrum_for_listen(force=True)
        self._capture = LoopbackCapture(device_index=idx)
        self._capture.start()
        self._smooth_state = None
        self._freq_smooth_state = None
        self._peak_state = None
        self._ring_buf = None
        self._ring_write = 0
        self._silent_ticks = 0
        self._tick_i = 0
        self._listening_status = False
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._btn_detect.setEnabled(False)
        self._timer.start()
        sr = self._capture.sample_rate
        self._set_status(f"● Listening @ {sr} Hz — waiting for audio…", ok=True)
        self._info.setText(
            f"Capturing · {sr} Hz · FFT {self._settings.n_fft} · "
            f"{self._settings.freq_scale} scale · all frequency bins"
        )

    def _stop(self) -> None:
        self._timer.stop()
        self._listening_status = False
        if self._capture:
            self._capture.stop()
            self._capture = None
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_detect.setEnabled(True)
        self._set_status("● Stopped", ok=None)

    def _tick(self) -> None:
        if not self._capture:
            return

        # Drain every pending chunk without blocking the Qt main thread.
        new_samples: list[np.ndarray] = []
        while True:
            chunk = self._capture.read(timeout=0)
            if chunk is None or len(chunk) == 0:
                break
            new_samples.append(chunk)

        if not new_samples:
            self._silent_ticks += 1
            if self._silent_ticks > _SILENT_TICKS_THRESHOLD:
                self._set_status(
                    "● No signal — try Auto-detect or another output device",
                    ok=False,
                )
            return

        self._silent_ticks = 0
        if not self._listening_status:
            self._listening_status = True
            self._set_status("● Listening — spectrum live", ok=True)

        s = self._settings
        sr = self._capture.sample_rate
        self._tick_i += 1

        # Append new audio into a rolling n_fft-sized ring buffer so the FFT
        # always sees a full window even when blocks are smaller than n_fft.
        new_audio = np.concatenate(new_samples)
        n_fft = s.n_fft
        if self._ring_buf is None or len(self._ring_buf) != n_fft:
            self._ring_buf = np.zeros(n_fft, dtype=np.float32)
            self._ring_write = 0
        n = min(len(new_audio), n_fft)
        w = self._ring_write
        if w + n <= n_fft:
            self._ring_buf[w : w + n] = new_audio[-n:].astype(np.float32, copy=False)
        else:
            first = n_fft - w
            self._ring_buf[w:] = new_audio[-n : -n + first].astype(np.float32, copy=False)
            self._ring_buf[: n - first] = new_audio[-n + first :].astype(
                np.float32, copy=False
            )
        self._ring_write = (w + n) % n_fft
        fft_samples = np.concatenate(
            (self._ring_buf[self._ring_write :], self._ring_buf[: self._ring_write])
        )

        freqs, db = compute_spectrum(fft_samples, sr, n_fft=n_fft)

        alpha_t = max(0.05, 1.0 - s.smoothing_time)
        db, self._smooth_state = smooth_temporal(db, alpha_t, self._smooth_state)

        decay = (s.db_max - s.db_min) / max(s.peak_hold_decay_sec * _TIMER_HZ, 1)
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

        self._spectrum.update_spectrum(x_disp, d_disp, p_disp, hz=hz_disp)
        if s.waterfall_enabled and self._tick_i % _WATERFALL_FRAME_SKIP == 0:
            self._waterfall.push_frame(x_disp, d_disp)
        if self._tick_i % _METRICS_INTERVAL == 0:
            peak_i = int(np.argmax(d_disp))
            peak_hz = float(hz_disp[peak_i]) if len(hz_disp) else 0
            rms = float(np.sqrt(np.mean(new_audio**2)))
            rms_db = 20 * np.log10(max(rms, 1e-9))
            self._metrics.setText(
                f"Peak: {peak_hz:,.0f} Hz · RMS: {rms_db:.1f} dB · "
                f"Bins: {len(hz_disp)} · Δf ≈ {sr / s.n_fft:.1f} Hz"
            )

    def shutdown(self) -> None:
        if self._probe_worker and self._probe_worker.isRunning():
            self._probe_worker.wait(3000)
        self._stop()
