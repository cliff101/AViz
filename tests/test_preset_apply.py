"""Preset application must not be overwritten by UI spinboxes."""

from aviz.visual_settings import (
    DB_DEFAULT_MAX,
    DB_DEFAULT_MIN,
    PRESETS,
    VisualSettings,
    apply_preset,
)


def test_apply_cinema_smoothing():
    base = VisualSettings(smoothing_time=0.1, smoothing_freq=0.05)
    s = apply_preset("cinema", base)
    assert s.preset_id == "cinema"
    assert s.smoothing_time == PRESETS["cinema"].smoothing_time
    assert s.db_min == DB_DEFAULT_MIN
    assert s.db_max == DB_DEFAULT_MAX
    assert s.colormap == "inferno"
    assert s.n_fft == base.n_fft


def test_preset_switch_keeps_db_range():
    base = VisualSettings(db_min=-40.0, db_max=90.0, n_fft=4096)
    clinical = apply_preset("clinical", base)
    assert clinical.db_min == -40.0
    assert clinical.db_max == 90.0
    assert clinical.n_fft == 4096
    cinema = apply_preset("cinema", clinical)
    assert cinema.db_min == -40.0
    assert cinema.db_max == 90.0
    assert cinema.colormap == "inferno"


def test_all_presets_share_default_db_window():
    for name in PRESETS:
        assert PRESETS[name].db_min == DB_DEFAULT_MIN
        assert PRESETS[name].db_max == DB_DEFAULT_MAX
