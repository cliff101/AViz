"""Lightweight UI smoke tests (no audio hardware)."""

import os

import pytest

pytest.importorskip("PySide6")

# Offscreen when supported (Linux CI); harmless on Windows if ignored
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_main_window_constructs(qapp):
    from aviz.ui.main_window import MainWindow

    win = MainWindow()
    assert win._tabs.count() == 3
    assert win._home is not None
    assert win._live is not None
    assert win._player is not None
    win.close()


def test_spectrum_widget_update(qapp):
    import numpy as np
    from aviz.ui.widgets.spectrum_plot import SpectrumPlotWidget

    w = SpectrumPlotWidget()
    f = np.logspace(np.log10(20), np.log10(8000), 200)
    db = -60 + 20 * np.random.randn(200)
    w.update_spectrum(f, db)
    w.close()


def test_visual_fx_emits(qapp):
    from aviz.ui.widgets.visual_fx_panel import VisualFxPanel
    from aviz.visual_settings import VisualSettings

    panel = VisualFxPanel()
    received = []

    panel.settings_changed.connect(lambda s: received.append(s))
    panel._preset.setCurrentText("neon")
    assert len(received) >= 1
    assert isinstance(received[-1], VisualSettings)
