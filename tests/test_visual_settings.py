"""Visual settings and presets."""

from aviz.visual_settings import PRESETS, VisualSettings, apply_preset


def test_defaults_roundtrip():
    s = VisualSettings()
    d = s.to_dict()
    s2 = VisualSettings.from_dict(d)
    assert s2.colormap == s.colormap
    assert s2.n_fft == s.n_fft


def test_apply_preset_cinema():
    s = apply_preset("cinema")
    assert s.preset_id == "cinema"
    assert s.colormap == "inferno"
    assert s.freq_scale == "mel"
    assert s.glow_enabled is True
    assert s.smoothing_time == 0.5


def test_default_scale_is_mel():
    assert VisualSettings().freq_scale == "mel"


def test_all_presets_exist():
    for pid in ("cinema", "clinical", "neon"):
        assert pid in PRESETS
        p = apply_preset(pid)
        assert p.db_max > p.db_min
