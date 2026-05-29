"""Scrolling live waterfall — frequency (Hz) vs time history."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg

from aviz.colormap import db_to_normalized, get_lut
from aviz.ui.plot_axes import scaled_linear_range, scaled_log_range
from aviz.ui.theme import BG_DARK
from aviz.visual_settings import DB_DEFAULT_MAX, DB_DEFAULT_MIN


class WaterfallPlotWidget(pg.PlotWidget):
    """History strip: X = frequency (linked to spectrum), Y = time frames."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent=parent, background=BG_DARK)
        self.setLabel("bottom", "Frequency")
        self.getAxis("bottom").setStyle(showValues=False)
        self.setLabel("left", "History")
        self.showGrid(x=False, y=False)
        self.setMaximumHeight(200)
        self.setMinimumHeight(120)

        self._img = pg.ImageItem(axisOrder="row-major")
        self.addItem(self._img)

        self._buffer: np.ndarray | None = None
        self._depth = 200
        self._colormap = "inferno"
        self._lut: np.ndarray | None = None
        self._db_min = DB_DEFAULT_MIN
        self._db_max = DB_DEFAULT_MAX
        self._gamma = 1.0
        self._freq_scale = "mel"
        self._f_min = 20.0
        self._f_max = 12_000.0
        self._scale_x = 1.0
        self._log_x = False
        self._last_x0 = 0.0
        self._last_span = 1.0
        self._floor_px = 0

    def _floor_pixel(self) -> int:
        norm = db_to_normalized(
            np.array([self._db_min]), self._db_min, self._db_max, self._gamma
        )[0]
        return int(np.clip(norm, 0, 1) * 255)

    def configure(
        self,
        *,
        colormap: str,
        db_min: float,
        db_max: float,
        gamma: float,
        depth: int,
        freq_scale: str,
        f_min_hz: float,
        f_max_hz: float,
        scale_x: float,
        reset_buffer: bool = False,
        x_linked: bool = False,
    ) -> None:
        depth = max(32, depth)
        db_changed = (db_min, db_max, gamma) != (
            self._db_min,
            self._db_max,
            self._gamma,
        )
        reset = (
            reset_buffer
            or depth != self._depth
            or colormap != self._colormap
            or db_changed
        )
        self._depth = depth
        if colormap != self._colormap:
            self._colormap = colormap
            self._lut = get_lut(colormap)
        self._db_min = db_min
        self._db_max = db_max
        self._gamma = gamma
        self._freq_scale = freq_scale
        self._f_min = f_min_hz
        self._f_max = f_max_hz
        self._scale_x = max(scale_x, 0.05)
        self._floor_px = self._floor_pixel()

        log_x = freq_scale == "log"
        if log_x != self._log_x:
            self._log_x = log_x
            self.setLogMode(x=log_x, y=False)

        if reset:
            self._buffer = None

        if not x_linked:
            x0, x1 = self._x_limits()
            self.setXRange(x0, x1, padding=0)
        self.setYRange(0, depth, padding=0)

    def clear_history(self) -> None:
        self._buffer = None
        self._img.clear()

    def _x_limits(self) -> tuple[float, float]:
        if self._freq_scale == "log":
            return scaled_log_range(self._f_min, self._f_max, self._scale_x)
        return scaled_linear_range(self._f_min, self._f_max, self._scale_x)

    def push_frame(self, x_coords: np.ndarray, db: np.ndarray) -> None:
        if len(x_coords) < 2 or len(db) < 2:
            return
        if self._lut is None:
            self._lut = get_lut(self._colormap)

        n_freq = len(db)
        if self._buffer is None or self._buffer.shape != (self._depth, n_freq):
            self._buffer = np.full(
                (self._depth, n_freq), self._floor_px, dtype=np.uint8
            )

        self._buffer = np.roll(self._buffer, -1, axis=0)
        norm = db_to_normalized(db, self._db_min, self._db_max, self._gamma)
        self._buffer[-1, :] = (np.clip(norm, 0, 1) * 255).astype(np.uint8)

        self._img.setImage(
            self._buffer,
            autoLevels=False,
            levels=(0, 255),
            lut=self._lut,
        )
        x0 = float(x_coords[0])
        x1 = float(x_coords[-1])
        span = max(x1 - x0, 1e-6)
        if abs(x0 - self._last_x0) > 1e-9 or abs(span - self._last_span) > 1e-9:
            self._last_x0 = x0
            self._last_span = span
            self._img.setRect(x0, 0, span, self._depth)
