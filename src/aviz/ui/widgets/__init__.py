from aviz.runtime import is_android

if is_android():
    from aviz.ui.widgets.plot_stub_android import (
        SpectrogramPlotWidget,
        SpectrumPlotWidget,
        WaterfallPlotWidget,
    )
else:
    from aviz.ui.widgets.spectrogram_plot import SpectrogramPlotWidget
    from aviz.ui.widgets.spectrum_plot import SpectrumPlotWidget
    from aviz.ui.widgets.waterfall_plot import WaterfallPlotWidget

from aviz.ui.widgets.visual_fx_panel import VisualFxPanel

__all__ = [
    "SpectrumPlotWidget",
    "SpectrogramPlotWidget",
    "WaterfallPlotWidget",
    "VisualFxPanel",
]
