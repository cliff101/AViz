"""Visual FX dock — colormap, dB range, smoothing, presets."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from aviz.analysis.freq_scales import FREQ_SCALE_OPTIONS
from aviz.visual_settings import (
    DB_DEFAULT_MAX,
    DB_DEFAULT_MIN,
    DB_LIMIT_MAX,
    DB_LIMIT_MIN,
    PRESETS,
    VisualSettings,
    apply_preset,
)


class VisualFxPanel(QWidget):
    settings_changed = Signal(object)
    reset_view_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._settings = VisualSettings()
        self._block = False

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)

        preset_row = QFormLayout()
        self._preset = QComboBox()
        self._preset.addItems(list(PRESETS.keys()))
        self._preset.currentTextChanged.connect(self._on_preset)
        preset_row.addRow("Preset", self._preset)
        layout.addLayout(preset_row)

        color_box = QGroupBox("Color & level")
        color_form = QFormLayout(color_box)
        self._cmap = QComboBox()
        self._cmap.addItems(["inferno", "viridis", "magma", "turbo", "gray", "cyan"])
        self._cmap.currentTextChanged.connect(self._emit)
        color_form.addRow("Colormap", self._cmap)

        self._db_min = self._slider_spin(DB_LIMIT_MIN, DB_LIMIT_MAX, DB_DEFAULT_MIN)
        self._db_max = self._slider_spin(DB_LIMIT_MIN, DB_LIMIT_MAX, DB_DEFAULT_MAX)
        color_form.addRow("dB floor", self._db_min[1])
        color_form.addRow("dB ceiling", self._db_max[1])
        self._gamma = QDoubleSpinBox()
        self._gamma.setRange(0.3, 3.0)
        self._gamma.setSingleStep(0.1)
        self._gamma.setValue(1.0)
        self._gamma.valueChanged.connect(self._emit)
        color_form.addRow("Gamma", self._gamma)
        layout.addWidget(color_box)

        freq_box = QGroupBox("Frequency axis")
        freq_form = QFormLayout(freq_box)
        self._freq_scale = QComboBox()
        for scale_id, label in FREQ_SCALE_OPTIONS:
            self._freq_scale.addItem(label, scale_id)
        self._freq_scale.setToolTip(
            "Mel: pitch bands (Cinema default).\n"
            "Focus: full spectrum, lows use most width.\n"
            "Log: equal octaves · Linear: equal Hz."
        )
        self._freq_scale.currentIndexChanged.connect(self._emit)
        freq_form.addRow("Frequency scale", self._freq_scale)
        self._fmin = QDoubleSpinBox()
        self._fmin.setRange(10, 5000)
        self._fmin.setValue(20)
        self._fmin.valueChanged.connect(self._emit)
        self._fmax = QDoubleSpinBox()
        self._fmax.setRange(500, 48000)
        self._fmax.setDecimals(2)
        self._fmax.setValue(12000.0)
        self._fmax.valueChanged.connect(self._emit)
        freq_form.addRow("Low cut (Hz)", self._fmin)
        freq_form.addRow("High cut (Hz)", self._fmax)
        self._grid = QCheckBox("Show grid")
        self._grid.setChecked(True)
        self._grid.toggled.connect(self._emit)
        freq_form.addRow(self._grid)
        layout.addWidget(freq_box)

        view_box = QGroupBox("Axis zoom (horizontal / vertical)")
        view_form = QFormLayout(view_box)
        self._scale_x = QDoubleSpinBox()
        self._scale_x.setRange(0.25, 8.0)
        self._scale_x.setSingleStep(0.1)
        self._scale_x.setDecimals(2)
        self._scale_x.setValue(1.0)
        self._scale_x.setToolTip(
            "Spectrum: frequency · Player heatmap: use wheel on chart (time/freq)"
        )
        self._scale_x.valueChanged.connect(self._emit)
        view_form.addRow("Horizontal", self._scale_x)
        self._scale_y = QDoubleSpinBox()
        self._scale_y.setRange(0.25, 8.0)
        self._scale_y.setSingleStep(0.1)
        self._scale_y.setDecimals(2)
        self._scale_y.setValue(1.0)
        self._scale_y.setToolTip("Spectrum level (dB) — higher = zoom in")
        self._scale_y.valueChanged.connect(self._emit)
        view_form.addRow("Vertical", self._scale_y)
        hint = QLabel(
            "Wheel on chart: left = vertical · center = both · right = horizontal\n"
            "(Live/spectrum: level / both / freq · Player heatmap: freq / both / time)\n"
            "Shift = horizontal only · Ctrl = vertical only"
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        view_form.addRow(hint)
        layout.addWidget(view_box)

        analysis_box = QGroupBox("Analysis")
        analysis_form = QFormLayout(analysis_box)
        self._n_fft = QComboBox()
        self._n_fft.addItems(["512", "1024", "2048", "4096", "8192"])
        self._n_fft.setCurrentText("2048")
        self._n_fft.currentTextChanged.connect(self._emit)
        analysis_form.addRow("FFT size", self._n_fft)
        self._smooth_t = self._slider_spin(0, 100, 50, suffix="%")
        self._smooth_f = self._slider_spin(0, 100, 20, suffix="%")
        analysis_form.addRow("Time smooth", self._smooth_t[1])
        analysis_form.addRow("Freq smooth", self._smooth_f[1])
        layout.addWidget(analysis_box)

        fx_box = QGroupBox("Effects")
        fx_form = QFormLayout(fx_box)
        self._peak = QCheckBox("Peak hold")
        self._peak.setChecked(True)
        self._peak.toggled.connect(self._emit)
        fx_form.addRow(self._peak)
        self._glow = QCheckBox("Glow on peaks")
        self._glow.setChecked(True)
        self._glow.toggled.connect(self._emit)
        fx_form.addRow(self._glow)
        self._waterfall = QCheckBox("Waterfall (live)")
        self._waterfall.toggled.connect(self._emit)
        fx_form.addRow(self._waterfall)
        self._style = QComboBox()
        self._style.addItems(["filled", "line", "bars"])
        self._style.currentTextChanged.connect(self._emit)
        fx_form.addRow("Spectrum style", self._style)
        layout.addWidget(fx_box)

        reset_btn = QPushButton("Reset to Cinema preset")
        reset_btn.clicked.connect(lambda: self._on_preset("cinema"))
        layout.addWidget(reset_btn)
        self._reset_view_btn = QPushButton("Reset chart pan/zoom")
        self._reset_view_btn.setToolTip("Fit axis to current FX limits")
        self._reset_view_btn.clicked.connect(self.reset_view_requested.emit)
        layout.addWidget(self._reset_view_btn)
        layout.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def _slider_spin(self, lo, hi, val, suffix=" dB"):
        slider = QSlider()
        slider.setOrientation(Qt.Orientation.Horizontal)
        spin = QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setValue(val)
        spin.setSuffix(suffix)
        spin.valueChanged.connect(lambda v: self._emit())
        return slider, spin

    def _on_preset(self, name: str) -> None:
        if self._block:
            return
        self._settings = apply_preset(name, self._settings)
        self.set_settings(self._settings)
        self.settings_changed.emit(self._settings)

    def set_settings(self, s: VisualSettings) -> None:
        self._block = True
        self._settings = s
        self._preset.blockSignals(True)
        self._preset.setCurrentText(s.preset_id if s.preset_id in PRESETS else "cinema")
        self._preset.blockSignals(False)
        self._cmap.setCurrentText(s.colormap)
        self._db_min[1].setValue(s.db_min)
        self._db_max[1].setValue(s.db_max)
        self._gamma.setValue(s.gamma)
        idx = self._freq_scale.findData(s.freq_scale)
        if idx < 0:
            idx = self._freq_scale.findData("mel")
        self._freq_scale.setCurrentIndex(max(idx, 0))
        self._fmin.setValue(s.freq_min_hz)
        self._fmax.setValue(s.freq_max_hz)
        self._scale_x.setValue(s.scale_x)
        self._scale_y.setValue(s.scale_y)
        self._grid.setChecked(s.show_grid)
        self._n_fft.setCurrentText(str(s.n_fft))
        self._smooth_t[1].setValue(s.smoothing_time * 100.0)
        self._smooth_f[1].setValue(s.smoothing_freq * 100.0)
        self._peak.setChecked(s.peak_hold_enabled)
        self._glow.setChecked(s.glow_enabled)
        self._waterfall.setChecked(s.waterfall_enabled)
        self._style.setCurrentText(s.spectrum_style)
        self._block = False

    def get_settings(self) -> VisualSettings:
        """Merge panel controls into current settings (preserve fields not in the UI)."""
        return replace(
            self._settings,
            preset_id=self._preset.currentText(),
            colormap=self._cmap.currentText(),
            db_min=self._db_min[1].value(),
            db_max=self._db_max[1].value(),
            gamma=self._gamma.value(),
            freq_scale=self._freq_scale.currentData() or "mel",
            freq_min_hz=self._fmin.value(),
            freq_max_hz=self._fmax.value(),
            scale_x=self._scale_x.value(),
            scale_y=self._scale_y.value(),
            show_grid=self._grid.isChecked(),
            n_fft=int(self._n_fft.currentText()),
            smoothing_time=self._smooth_t[1].value() / 100.0,
            smoothing_freq=self._smooth_f[1].value() / 100.0,
            peak_hold_enabled=self._peak.isChecked(),
            glow_enabled=self._glow.isChecked(),
            waterfall_enabled=self._waterfall.isChecked(),
            spectrum_style=self._style.currentText(),
        )

    def _emit(self) -> None:
        if self._block:
            return
        self._settings = self.get_settings()
        self.settings_changed.emit(self._settings)
