"""Colormap and dB normalization tests."""

import numpy as np
import pytest

from aviz.colormap import db_to_normalized, get_lut


@pytest.mark.parametrize("name", ["inferno", "viridis", "gray", "cyan", "magma", "turbo"])
def test_lut_shape(name: str):
    lut = get_lut(name, 256)
    assert lut.shape == (256, 4)
    assert lut.dtype == np.uint8


def test_db_to_normalized_range():
    db = np.array([-80.0, -50.0, -20.0])
    norm = db_to_normalized(db, -80, -20)
    assert norm[0] == pytest.approx(0.0)
    assert norm[-1] == pytest.approx(1.0)


def test_db_gamma():
    db = np.array([-50.0])
    n1 = db_to_normalized(db, -80, -20, gamma=1.0)
    n2 = db_to_normalized(db, -80, -20, gamma=2.0)
    assert n2[0] < n1[0]
