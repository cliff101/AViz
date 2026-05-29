"""Visual FX settings shared by Live and File modes."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

DB_LIMIT_MIN = -200.0
DB_LIMIT_MAX = 200.0
DB_DEFAULT_MIN = -50.0
DB_DEFAULT_MAX = 70.0


@dataclass
class VisualSettings:
    preset_id: str = "cinema"
    colormap: str = "inferno"
    db_min: float = DB_DEFAULT_MIN
    db_max: float = DB_DEFAULT_MAX
    gamma: float = 1.0
    auto_gain: bool = False
    freq_scale: str = "mel"  # mel | focus | log | linear
    freq_min_hz: float = 20.0
    freq_max_hz: float = 12_000.0
    scale_x: float = 1.0  # spectrum / live: frequency zoom (>1 = zoom in)
    scale_y: float = 1.0  # spectrum / live: level (dB) zoom
    heatmap_scale_x: float = 1.0  # player heatmap: time zoom
    heatmap_scale_y: float = 1.0  # player heatmap: frequency zoom
    heatmap_center_mode: bool = False  # keep playhead centered on time axis
    show_grid: bool = True
    n_fft: int = 2048
    overlap_pct: float = 50.0
    smoothing_time: float = 0.15
    smoothing_freq: float = 0.2
    peak_hold_enabled: bool = True
    peak_hold_decay_sec: float = 2.0
    glow_enabled: bool = True
    glow_threshold_db: float = -40.0
    waterfall_enabled: bool = False
    waterfall_depth: int = 200
    spectrum_style: str = "filled"  # filled | bars | line
    show_band_meters: bool = True
    show_mini_spectrum: bool = True
    playhead_highlight: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> VisualSettings:
        if not data:
            return cls()
        from aviz.analysis.freq_scales import normalize_freq_scale

        fields = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in fields}
        if "freq_scale" in filtered:
            filtered["freq_scale"] = normalize_freq_scale(str(filtered["freq_scale"]))
        return cls(**filtered)


PRESETS: dict[str, VisualSettings] = {
    "cinema": VisualSettings(
        preset_id="cinema",
        colormap="inferno",
        gamma=1.0,
        freq_scale="mel",
        freq_min_hz=20.0,
        freq_max_hz=12_000.0,
        scale_x=1.0,
        scale_y=1.0,
        smoothing_time=0.15,
        smoothing_freq=0.3,
        glow_enabled=True,
        glow_threshold_db=-45.0,
        peak_hold_enabled=True,
        peak_hold_decay_sec=2.0,
        show_grid=True,
        spectrum_style="filled",
        waterfall_depth=200,
    ),
    "clinical": VisualSettings(
        preset_id="clinical",
        colormap="gray",
        freq_scale="linear",
        smoothing_time=0.1,
        glow_enabled=True,
        glow_threshold_db=-40.0,
        peak_hold_enabled=True,
        peak_hold_decay_sec=2.0,
    ),
    "neon": VisualSettings(
        preset_id="neon",
        colormap="cyan",
        freq_scale="log",
        smoothing_time=0.12,
        glow_enabled=True,
        peak_hold_decay_sec=3.0,
    ),
}


def apply_preset(preset_id: str, base: VisualSettings | None = None) -> VisualSettings:
    if preset_id not in PRESETS:
        return base or VisualSettings()
    p = deepcopy(PRESETS[preset_id])
    if base is not None:
        # Keep analysis window and level range — presets only change look & scale style
        p.n_fft = base.n_fft
        p.db_min = base.db_min
        p.db_max = base.db_max
        p.scale_x = base.scale_x
        p.scale_y = base.scale_y
        p.heatmap_scale_x = base.heatmap_scale_x
        p.heatmap_scale_y = base.heatmap_scale_y
        p.heatmap_center_mode = base.heatmap_center_mode
    return p
