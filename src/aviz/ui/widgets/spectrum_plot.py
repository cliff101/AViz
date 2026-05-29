"""Full-spectrum analyzer plot — frequency (Hz) vs dB for all bins."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QWheelEvent
from PySide6.QtWidgets import QApplication

from aviz.colormap import get_lut
from aviz.analysis.freq_scales import normalize_freq_scale, uses_warped_x_axis
from aviz.ui.freq_axis import FrequencyScaleAxis, axis_label_for_scale
from aviz.ui.plot_axes import apply_wheel_zoom, scaled_linear_range, scaled_log_range
from aviz.ui.theme import ACCENT, BG_DARK, TEXT_MUTED
from aviz.ui.widgets.viewbox_guard import ViewBoxGuardMixin
from aviz.visual_settings import DB_DEFAULT_MAX, DB_DEFAULT_MIN


def _bar_widths(x: np.ndarray, *, fraction: float = 0.85) -> np.ndarray | float:
    """Per-bar width from neighbor spacing in display coordinates."""
    n = len(x)
    if n < 2:
        return 1.0
    dx = np.diff(x)
    w = np.empty(n, dtype=np.float64)
    w[0] = dx[0]
    w[-1] = dx[-1]
    if n > 2:
        w[1:-1] = np.minimum(dx[:-1], dx[1:])
    return w * fraction


def _enable_clip_to_view(item: pg.GraphicsItem) -> None:
    """pyqtgraph: PlotDataItem has setClipToView; PlotCurveItem may not."""
    if hasattr(item, "setClipToView"):
        item.setClipToView(True)
    elif hasattr(item, "opts"):
        item.opts["clipToView"] = True


class SpectrumPlotWidget(ViewBoxGuardMixin, pg.PlotWidget):
  def __init__(self, parent=None) -> None:
    super().__init__(parent=parent, background=BG_DARK)
    self._freq_axis = FrequencyScaleAxis(orientation="bottom")
    self.plotItem.setAxisItems({"bottom": self._freq_axis})
    self.setLabel("bottom", "Frequency", units=axis_label_for_scale("mel"))
    self.setLabel("left", "Level", units="dB")
    self._last_display_x: np.ndarray | None = None
    self._last_display_hz: np.ndarray | None = None
    self.showGrid(x=True, y=True, alpha=0.15)
    vb = self.getViewBox()
    vb.enableAutoRange(pg.ViewBox.XAxis, False)
    vb.enableAutoRange(pg.ViewBox.YAxis, False)
    vb.setAutoVisible(x=False, y=False)
    self.plotItem.setAutoVisible(x=False, y=False)
    self._init_view_guard()

    self._log_x = False
    self._freq_scale = "mel"
    self._f_min = 20.0
    self._f_max = 12000.0
    self._db_min = DB_DEFAULT_MIN
    self._db_max = DB_DEFAULT_MAX
    self._scale_x = 1.0
    self._scale_y = 1.0
    self._prev_scale_x = 1.0
    self._prev_scale_y = 1.0

    self.setLogMode(x=False, y=False)
    self.apply_axis_view(
      freq_scale="mel",
      f_min_hz=20.0,
      f_max_hz=12000.0,
      db_min=DB_DEFAULT_MIN,
      db_max=DB_DEFAULT_MAX,
      scale_x=1.0,
      scale_y=1.0,
      force=True,
    )

    self._bars = pg.BarGraphItem(
      x=[0, 1],
      height=[0, 0],
      y0=DB_DEFAULT_MIN,
      width=1.0,
      brush=pg.mkBrush(QColor(ACCENT)),
      pen=pg.mkPen(ACCENT, width=1),
    )
    _enable_clip_to_view(self._bars)
    self._bars.hide()

    self._curve = pg.PlotCurveItem(pen=pg.mkPen(ACCENT, width=2))
    _enable_clip_to_view(self._curve)
    self._peak_curve = pg.PlotCurveItem(
      pen=pg.mkPen(QColor(255, 180, 50), width=3, style=Qt.PenStyle.DashLine)
    )
    _enable_clip_to_view(self._peak_curve)
    self._glow_curve = pg.PlotCurveItem(
      pen=pg.mkPen(ACCENT, width=4), brush=None
    )
    _enable_clip_to_view(self._glow_curve)
    self.addItem(self._bars)
    self.addItem(self._curve)
    self.addItem(self._glow_curve)
    self.addItem(self._peak_curve)
    self._bars.setZValue(3)
    self._glow_curve.setZValue(5)
    self._peak_curve.setZValue(6)
    self._curve.setZValue(4)

    self._show_peak = True
    self._show_glow = True
    self._glow_threshold = -40.0
    self._colormap = "inferno"
    self._db_min = DB_DEFAULT_MIN
    self._db_max = DB_DEFAULT_MAX
    self._spectrum_style = "filled"
    self._axis_tick_key: tuple | None = None
    self._last_pen_rgb: tuple[int, int, int] | None = None
    self._plot_len = 0
    self._wheel_axis_pick = False

    self._crosshair_v = pg.InfiniteLine(
      angle=90, movable=False, pen=pg.mkPen(TEXT_MUTED, width=1, style=Qt.PenStyle.DotLine)
    )
    self.addItem(self._crosshair_v)
    self._crosshair_v.hide()
    self.scene().sigMouseMoved.connect(self._on_mouse)

  def set_wheel_axis_pick(self, enabled: bool) -> None:
    """Wheel: left = vertical · center = both · right = horizontal."""
    self._wheel_axis_pick = enabled

  def wheelEvent(self, ev: QWheelEvent) -> None:
    if apply_wheel_zoom(
      self.getViewBox(),
      ev,
      self.width(),
      self.height(),
      axis_pick=self._wheel_axis_pick,
    ):
      self._mark_user_zoom()
      ev.accept()

  def set_show_peak(self, on: bool) -> None:
    self._show_peak = on
    self._peak_curve.setVisible(on)

  def set_show_glow(self, on: bool, threshold_db: float = -40.0) -> None:
    self._show_glow = on
    self._glow_threshold = threshold_db
    self._glow_curve.setVisible(on)

  def set_colormap(self, name: str) -> None:
    self._colormap = name

  def set_spectrum_style(self, style: str) -> None:
    style = style if style in ("filled", "line", "bars") else "filled"
    self._spectrum_style = style
    self._plot_len = 0
    is_bars = style == "bars"
    self._bars.setVisible(is_bars)
    self._curve.setVisible(not is_bars)
    if self._show_glow:
      self._glow_curve.setVisible(not is_bars)

  def _color_from_colormap(self, db_value: float) -> tuple[int, int, int]:
    lut = get_lut(self._colormap)
    norm = (db_value - self._db_min) / max(self._db_max - self._db_min, 1e-6)
    idx = int(np.clip(norm, 0.0, 1.0) * (len(lut) - 1))
    r, g, b = int(lut[idx, 0]), int(lut[idx, 1]), int(lut[idx, 2])
    return r, g, b

  def _x_limits(
    self, freq_scale: str, f_min_hz: float, f_max_hz: float, scale_x: float
  ) -> tuple[float, float]:
    scale = normalize_freq_scale(freq_scale)
    if scale == "log":
      return scaled_log_range(f_min_hz, f_max_hz, scale_x)
    if uses_warped_x_axis(scale):
      return scaled_linear_range(0.0, 1.0, scale_x)
    return scaled_linear_range(f_min_hz, f_max_hz, scale_x)

  def update_display_metadata(
    self,
    freq_scale: str,
    f_min_hz: float,
    f_max_hz: float,
    db_min: float,
    db_max: float,
    scale_x: float,
    scale_y: float,
  ) -> None:
    self._freq_scale = freq_scale
    self._f_min = f_min_hz
    self._f_max = f_max_hz
    self._db_min = db_min
    self._db_max = db_max
    self._scale_x = max(scale_x, 0.05)
    self._scale_y = max(scale_y, 0.05)
    self._axis_tick_key = None

  def apply_axis_view(
    self,
    freq_scale: str,
    f_min_hz: float,
    f_max_hz: float,
    db_min: float,
    db_max: float,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    force: bool = False,
    update_x: bool = True,
    update_y: bool = True,
  ) -> None:
    """Set axis limits from FX. Skipped when user has panned/zoomed unless force."""
    self._freq_scale = freq_scale
    self._f_min = f_min_hz
    self._f_max = f_max_hz
    self._db_min = db_min
    self._db_max = db_max
    self._scale_x = max(scale_x, 0.05)
    self._scale_y = max(scale_y, 0.05)

    if self._user_transformed and not force:
      return

    scale = normalize_freq_scale(freq_scale)
    log_x = scale == "log"
    if log_x != self._log_x:
      self._programmatic_range = True
      try:
        self._log_x = log_x
        self.setLogMode(x=log_x, y=False)
      finally:
        self._programmatic_range = False

    if update_y:
      y0, y1 = scaled_linear_range(db_min, db_max, self._scale_y)
      self._set_view_range(y_range=(y0, y1))
    if update_x:
      x0, x1 = self._x_limits(freq_scale, f_min_hz, f_max_hz, self._scale_x)
      self._set_view_range(x_range=(x0, x1))
    self._prev_scale_x = self._scale_x
    self._prev_scale_y = self._scale_y
    self._axis_tick_key = None
    self._sync_freq_axis_ticks()

  def _sync_freq_axis_ticks(self) -> None:
    self.setLabel("bottom", "Frequency", units=axis_label_for_scale(self._freq_scale))
    self._freq_axis.configure(
      self._freq_scale,
      f_min=self._f_min,
      f_max=self._f_max,
      display_hz=self._last_display_hz,
    )

  def apply_db_axis(
    self,
    db_min: float,
    db_max: float,
    scale_y: float | None = None,
  ) -> None:
    """Update Y limits from dB floor/ceiling (always applies, even after user pan/zoom)."""
    self._db_min = db_min
    self._db_max = db_max
    if scale_y is not None:
      self._scale_y = max(scale_y, 0.05)
    y0, y1 = scaled_linear_range(self._db_min, self._db_max, self._scale_y)
    self._set_view_range(y_range=(y0, y1))
    self._prev_scale_y = self._scale_y

  def frequency_view_corrupt(self) -> bool:
    """Detect broken X range (e.g. axis stuck near 0 Hz). Never flags user pan/zoom."""
    if self._user_transformed:
      return False
    scale = normalize_freq_scale(self._freq_scale)
    if (scale == "log") != self._log_x:
      return True
    xr, _ = self._view_range()
    span = max(xr[1] - xr[0], 0.0)
    if uses_warped_x_axis(self._freq_scale):
      # Valid view is a sub-range of [0, 1]; only flag obvious garbage
      return span > 1.5 or xr[1] < -0.5 or xr[0] > 1.5
    if self._freq_scale == "log":
      lo = max(self._f_min, 1.0)
      return span > 12 or xr[1] < lo * 0.01 or xr[0] > self._f_max * 100
    expected = max(self._f_max - self._f_min, 1.0)
    if xr[1] < self._f_min * 0.1 or xr[0] > self._f_max * 2.0:
      return True
    return span > expected * 5.0

  def repair_frequency_axis(self) -> None:
    """Restore frequency axis to FX limits when view range is invalid."""
    x0, x1 = self._x_limits(
      self._freq_scale, self._f_min, self._f_max, self._scale_x
    )
    self._set_view_range(x_range=(x0, x1))
    self._prev_scale_x = self._scale_x

  def set_frequency_scale_mode(self, freq_scale: str) -> None:
    """Switch log mode on X when needed (does not reset zoom)."""
    freq_scale = normalize_freq_scale(freq_scale)
    log_x = freq_scale == "log"
    if log_x == self._log_x:
      return
    self._freq_scale = freq_scale
    self._programmatic_range = True
    try:
      self._log_x = log_x
      self.setLogMode(x=log_x, y=False)
    finally:
      self._programmatic_range = False
    self._sync_freq_axis_ticks()

  def apply_horizontal_zoom(self, new_scale: float, old_scale: float) -> None:
    """Zoom frequency axis only; higher scale = zoom in."""
    if old_scale <= 0 or abs(new_scale - old_scale) < 1e-9:
      return
    xr, _ = self._view_range()
    cx = (xr[0] + xr[1]) / 2.0
    half = max((xr[1] - xr[0]) / 2.0, 1e-12)
    new_half = half * (old_scale / new_scale)
    self._set_view_range(x_range=(cx - new_half, cx + new_half))
    self._scale_x = max(new_scale, 0.05)
    self._prev_scale_x = self._scale_x

  def apply_vertical_zoom(self, new_scale: float, old_scale: float) -> None:
    """Zoom dB axis only; higher scale = zoom in."""
    if old_scale <= 0 or abs(new_scale - old_scale) < 1e-9:
      return
    _, yr = self._view_range()
    cy = (yr[0] + yr[1]) / 2.0
    half = max((yr[1] - yr[0]) / 2.0, 1e-12)
    new_half = half * (old_scale / new_scale)
    self._set_view_range(y_range=(cy - new_half, cy + new_half))
    self._scale_y = max(new_scale, 0.05)
    self._prev_scale_y = self._scale_y

  def reset_plot_cache(self) -> None:
    """Force full curve rebuild after frequency scale / bin count changes."""
    self._plot_len = 0
    self._axis_tick_key = None

  def ensure_view_coherent(
    self,
    freq_scale: str,
    f_min_hz: float,
    f_max_hz: float,
    db_min: float,
    db_max: float,
    scale_x: float,
    scale_y: float,
    *,
    force: bool = False,
  ) -> None:
    """Match log mode and X limits to the active frequency scale (fixes tab-switch glitches)."""
    scale = normalize_freq_scale(freq_scale)
    if (scale == "log") != self._log_x:
      force = True
    if normalize_freq_scale(self._freq_scale) != scale:
      force = True
    if self.frequency_view_corrupt():
      self.reset_user_view()
      force = True
    self.apply_axis_view(
      freq_scale,
      f_min_hz,
      f_max_hz,
      db_min,
      db_max,
      scale_x,
      scale_y,
      force=force,
    )

  def _sync_axis_ticks(self, hz_arr: np.ndarray | None) -> None:
    key = (self._freq_scale, round(self._f_min), round(self._f_max))
    if key == self._axis_tick_key:
      return
    self._axis_tick_key = key
    self._freq_axis.configure(
      self._freq_scale,
      f_min=self._f_min,
      f_max=self._f_max,
      display_hz=hz_arr,
    )

  def _sort_xy(
    self, f: np.ndarray, d: np.ndarray
  ) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    if len(f) < 2 or not np.any(np.diff(f) <= 0):
      return f, d, None
    order = np.argsort(f, kind="stable")
    return f[order], d[order], order

  def _dedupe_x(
    self, f: np.ndarray, d: np.ndarray, peaks: np.ndarray | None
  ) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Drop duplicate X so fill/stroke paths cannot self-intersect."""
    if len(f) < 2:
      return f, d, peaks
    span = max(float(f[-1] - f[0]), 1e-9)
    keep = np.concatenate(([True], np.diff(f) > span * 1e-9))
    if np.all(keep):
      return f, d, peaks
    f, d = f[keep], d[keep]
    if peaks is not None and len(peaks) == len(keep):
      peaks = peaks[keep]
    return f, d, peaks

  def _set_main_curve(
    self, f: np.ndarray, d: np.ndarray, rgb: tuple[int, int, int], *, skip: bool
  ) -> None:
    kw: dict = {"skipFiniteCheck": skip, "connect": "finite"}
    if self._spectrum_style == "filled":
      kw["fillLevel"] = self._db_min
      kw["brush"] = pg.mkBrush(rgb[0], rgb[1], rgb[2], 70)
      self._curve.setPen(pg.mkPen(rgb, width=2))
    elif self._spectrum_style == "line":
      self._curve.setBrush(pg.mkBrush(0, 0, 0, 0))
      self._curve.setPen(pg.mkPen(rgb, width=2))
    self._curve.setData(f, d, **kw)

  def _set_bars(
    self, f: np.ndarray, d: np.ndarray, rgb: tuple[int, int, int], *, skip: bool
  ) -> None:
    heights = np.maximum(d - self._db_min, 0.0)
    self._bars.setOpts(
      x=f,
      height=heights,
      y0=self._db_min,
      width=_bar_widths(f),
      brush=pg.mkBrush(rgb[0], rgb[1], rgb[2], 200),
      pen=pg.mkPen(rgb, width=1),
    )

  def update_spectrum(
    self,
    x: np.ndarray,
    db: np.ndarray,
    peaks: np.ndarray | None = None,
    *,
    hz: np.ndarray | None = None,
  ) -> None:
    if len(x) < 2:
      return
    hz_arr = hz if hz is not None else x
    self._last_display_x = x
    self._last_display_hz = hz_arr
    self._sync_axis_ticks(hz_arr)

    valid = np.isfinite(x)
    f = x[valid]
    d = np.clip(db[valid], self._db_min, self._db_max)
    n = len(f)
    if n < 2:
      return

    f, d, order = self._sort_xy(f, d)
    if peaks is not None and len(peaks) == len(x):
      peaks = peaks[valid]
      if order is not None:
        peaks = peaks[order]
    f, d, peaks = self._dedupe_x(f, d, peaks)
    n = len(f)
    if n < 2:
      return

    peak_db = float(np.max(d))
    rgb = self._color_from_colormap(peak_db)

    if rgb != self._last_pen_rgb:
      self._last_pen_rgb = rgb
      if self._spectrum_style != "bars":
        self._curve.setPen(pg.mkPen(rgb, width=2))
      if self._show_glow and self._spectrum_style != "bars":
        self._glow_curve.setPen(pg.mkPen(rgb, width=4))

    refresh = n != self._plot_len
    self._plot_len = n
    if self._spectrum_style == "bars":
      self._set_bars(f, d, rgb, skip=not refresh)
    else:
      self._set_main_curve(f, d, rgb, skip=not refresh)

    if self._show_glow and self._spectrum_style != "bars":
      thr = min(self._glow_threshold, peak_db - 8.0)
      glow_d = np.where(d >= thr, d, np.nan)
      self._glow_curve.setData(f, glow_d, skipFiniteCheck=True, connect="finite")
    elif self._glow_curve.isVisible():
      self._glow_curve.setData([], [])

    if self._show_peak and peaks is not None and len(peaks) == n:
      self._peak_curve.setData(
        f,
        np.clip(peaks, self._db_min, self._db_max),
        skipFiniteCheck=not refresh,
        connect="finite",
      )
    elif self._peak_curve.isVisible() and peaks is None:
      self._peak_curve.setData([], [])

  def _on_mouse(self, pos) -> None:
    if QApplication.mouseButtons() != Qt.MouseButton.NoButton:
      return
    if not self.scene().sceneRect().contains(pos):
      return
    mouse = self.plotItem.vb.mapSceneToView(pos)
    self._crosshair_v.setPos(mouse.x())
    self._crosshair_v.show()

  def hide_crosshair(self) -> None:
    self._crosshair_v.hide()
