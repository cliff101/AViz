"""Lightweight plot placeholders on Android (pyqtgraph crashes natively in APK)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_MSG = (
    "Charts are disabled on Android in this build.\n"
    "Home, playlists, and file playback still work."
)


class _FakeViewBox:
    def setXLink(self, _other: object) -> None:
        pass

    def enableAutoRange(self, *_a: object, **_kw: object) -> None:
        pass

    def setAutoVisible(self, **_kw: object) -> None:
        pass


class _PlotStub(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(_MSG)
        label.setWordWrap(True)
        layout.addWidget(label)
        self._viewbox = _FakeViewBox()

    def getViewBox(self) -> _FakeViewBox:
        return self._viewbox

    def set_wheel_axis_pick(self, _enabled: bool) -> None:
        pass

    def reset_user_view(self) -> None:
        pass

    def reset_plot_cache(self) -> None:
        pass

    def user_view_active(self) -> bool:
        return False

    def apply_axis_view(self, **_kw: object) -> None:
        pass

    def ensure_view_coherent(self, **_kw: object) -> None:
        pass

    def update_spectrum(self, *_a: object, **_kw: object) -> None:
        pass


class SpectrumPlotWidget(_PlotStub):
    pass


class WaterfallPlotWidget(_PlotStub):
    def clear_history(self) -> None:
        pass

    def configure(self, **_kw: object) -> None:
        pass

    def push_frame(self, *_a: object, **_kw: object) -> None:
        pass


class SpectrogramPlotWidget(_PlotStub):
    playhead_clicked = Signal(float)

    def set_center_mode(self, _on: bool) -> None:
        pass

    def set_playhead(self, *_a: object, **_kw: object) -> None:
        pass

    def set_colormap(self, _name: str) -> None:
        pass

    def set_db_range(self, *_a: object, **_kw: object) -> None:
        pass

    def set_spectrogram(self, *_a: object, **_kw: object) -> None:
        pass
