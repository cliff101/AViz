"""Heatmap spectrogram with playhead."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QWheelEvent

from aviz.analysis.spectrogram import SpectrogramResult
from aviz.colormap import db_to_normalized, get_lut
from aviz.ui.plot_axes import apply_wheel_zoom, scaled_linear_range
from aviz.ui.theme import ACCENT, BG_DARK
from aviz.ui.widgets.viewbox_guard import ViewBoxGuardMixin
from aviz.visual_settings import DB_DEFAULT_MAX, DB_DEFAULT_MIN


class SpectrogramPlotWidget(ViewBoxGuardMixin, pg.PlotWidget):
  playhead_clicked = Signal(float)

  def __init__(self, parent=None) -> None:
    super().__init__(parent=parent, background=BG_DARK)
    self.setLabel("bottom", "Time", units="s")
    self.setLabel("left", "Frequency", units="Hz")
    self.setLogMode(x=False, y=False)
    self._img = pg.ImageItem(axisOrder="row-major")
    self.addItem(self._img)
    self._playhead = pg.InfiniteLine(
      angle=90,
      movable=False,
      pen=pg.mkPen(ACCENT, width=2),
    )
    self.addItem(self._playhead)
    vb = self.getViewBox()
    vb.enableAutoRange(pg.ViewBox.XAxis, False)
    vb.enableAutoRange(pg.ViewBox.YAxis, False)
    vb.setAutoVisible(x=False, y=False)
    self.plotItem.setAutoVisible(x=False, y=False)
    self._init_view_guard()

    self._result: SpectrogramResult | None = None
    self._db_min = DB_DEFAULT_MIN
    self._db_max = DB_DEFAULT_MAX
    self._gamma = 1.0
    self._cmap = "inferno"
    self._t0 = self._t1 = 0.0
    self._f0 = self._f1 = 0.0
    self._scale_x = 1.0
    self._scale_y = 1.0
    self._wheel_axis_pick = False
    self._center_mode = False

  def set_wheel_axis_pick(self, enabled: bool) -> None:
    """Wheel: left = frequency · center = both · right = time."""
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

  def set_colormap(self, name: str) -> None:
    self._cmap = name
    if self._result:
      self._run_preserve_view(self._apply_image)

  def set_db_range(self, db_min: float, db_max: float, gamma: float = 1.0) -> None:
    self._db_min = db_min
    self._db_max = db_max
    self._gamma = gamma
    if self._result:
      self._run_preserve_view(self._apply_image)

  def apply_axis_view(
    self,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    force: bool = False,
  ) -> None:
    self._scale_x = max(scale_x, 0.05)
    self._scale_y = max(scale_y, 0.05)
    if not self._result:
      return
    if self._user_transformed and not force:
      return
    x0, x1 = scaled_linear_range(self._t0, self._t1, self._scale_x)
    y0, y1 = scaled_linear_range(self._f0, self._f1, self._scale_y)
    self._set_view_range(x_range=(x0, x1), y_range=(y0, y1))

  def apply_horizontal_zoom(self, new_scale: float, old_scale: float) -> None:
    if old_scale <= 0 or abs(new_scale - old_scale) < 1e-9:
      return
    xr, _ = self._view_range()
    cx = (xr[0] + xr[1]) / 2.0
    half = max((xr[1] - xr[0]) / 2.0, 1e-12)
    new_half = half * (old_scale / new_scale)
    self._set_view_range(x_range=(cx - new_half, cx + new_half))

  def apply_vertical_zoom(self, new_scale: float, old_scale: float) -> None:
    if old_scale <= 0 or abs(new_scale - old_scale) < 1e-9:
      return
    _, yr = self._view_range()
    cy = (yr[0] + yr[1]) / 2.0
    half = max((yr[1] - yr[0]) / 2.0, 1e-12)
    new_half = half * (old_scale / new_scale)
    self._set_view_range(y_range=(cy - new_half, cy + new_half))

  def set_spectrogram(self, result: SpectrogramResult) -> None:
    self._result = result
    self._t0 = float(result.times[0])
    self._t1 = float(result.times[-1])
    self._f0 = float(result.frequencies[0])
    self._f1 = float(result.frequencies[-1])
    self.reset_user_view()
    self._apply_image()
    self.apply_axis_view(self._scale_x, self._scale_y, force=True)
    self._playhead.setPos(self._t0)

  def set_center_mode(self, on: bool) -> None:
    """When on, the time view pans so the playhead stays horizontally centered."""
    self._center_mode = on
    if on and self._result is not None:
      self.set_playhead(float(self._playhead.value()), center_follow=True)

  def set_playhead(self, seconds: float, *, center_follow: bool | None = None) -> None:
    self._playhead.setPos(seconds)
    if center_follow is None:
      center_follow = self._center_mode
    if not center_follow or self._result is None:
      return
    xr, _ = self._view_range()
    half = max((xr[1] - xr[0]) / 2.0, 1e-9)
    x0 = seconds - half
    x1 = seconds + half
    span = self._t1 - self._t0
    if 2 * half >= span:
      x0, x1 = self._t0, self._t1
    else:
      if x0 < self._t0:
        x0, x1 = self._t0, self._t0 + 2 * half
      if x1 > self._t1:
        x1, x0 = self._t1, self._t1 - 2 * half
    self._set_view_range(x_range=(x0, x1))

  def _apply_image(self) -> None:
    if not self._result:
      return
    r = self._result
    norm = db_to_normalized(r.db, self._db_min, self._db_max, self._gamma)
    lut = get_lut(self._cmap)
    indices = (norm * (len(lut) - 1)).astype(np.int32)
    rgba = lut[np.clip(indices, 0, len(lut) - 1)]
    self._img.setImage(rgba, autoLevels=False)
    self._img.setRect(
      pg.QtCore.QRectF(self._t0, self._f0, self._t1 - self._t0, self._f1 - self._f0)
    )

  def mouseClickEvent(self, ev) -> None:
    if ev.button() == Qt.MouseButton.LeftButton and self._result:
      pos = self.plotItem.vb.mapSceneToView(ev.scenePos())
      self.playhead_clicked.emit(float(pos.x()))
    super().mouseClickEvent(ev)
