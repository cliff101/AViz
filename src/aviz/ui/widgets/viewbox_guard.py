"""Preserve user pan/zoom when plot data or unrelated FX settings change."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyqtgraph as pg

if TYPE_CHECKING:
    from pyqtgraph import PlotWidget


class ViewBoxGuardMixin:
    """Mixin for PlotWidget subclasses — call _init_view_guard() from __init__."""

    _programmatic_range: bool
    _preserving_view: bool
    _user_transformed: bool

    def _init_view_guard(self) -> None:
        self._programmatic_range = False
        self._preserving_view = False
        self._user_transformed = False
        vb = self.getViewBox()
        vb.sigRangeChanged.connect(self._on_view_range_changed)

    def user_view_active(self) -> bool:
        return self._user_transformed

    def reset_user_view(self) -> None:
        self._user_transformed = False

    def _on_view_range_changed(self) -> None:
        if self._programmatic_range or self._preserving_view:
            return
        self._user_transformed = True

    def _view_range(self) -> tuple[tuple[float, float], tuple[float, float]]:
        xr, yr = self.getViewBox().viewRange()
        return (float(xr[0]), float(xr[1])), (float(yr[0]), float(yr[1]))

    def _set_view_range(
        self,
        x_range: tuple[float, float] | None = None,
        y_range: tuple[float, float] | None = None,
    ) -> None:
        self._programmatic_range = True
        try:
            vb = self.getViewBox()
            if x_range is not None:
                vb.setXRange(x_range[0], x_range[1], padding=0)
            if y_range is not None:
                vb.setYRange(y_range[0], y_range[1], padding=0)
        finally:
            self._programmatic_range = False

    def _run_preserve_view(self, fn) -> None:
        """Run fn for FX-driven redraws that might touch the view range."""
        self._preserving_view = True
        try:
            fn()
        finally:
            self._preserving_view = False

    def _mark_user_zoom(self) -> None:
        self._user_transformed = True
