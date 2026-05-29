"""Colormap LUTs for spectrograms and premium styling."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def get_lut(name: str, n: int = 256) -> NDArray[np.uint8]:
    """Return (n, 4) RGBA uint8 lookup table."""
    name = name.lower()
    if name == "gray" or name == "clinical":
        g = np.linspace(0, 255, n, dtype=np.uint8)
        return np.column_stack([g, g, g, np.full(n, 255, dtype=np.uint8)])
    if name == "cyan" or name == "neon":
        return _build_gradient_lut(n, (0, 20, 40), (0, 200, 255), (200, 50, 255))
    if name == "viridis":
        return _matplotlib_lut("viridis", n)
    if name == "magma":
        return _matplotlib_lut("magma", n)
    if name == "turbo":
        return _matplotlib_lut("turbo", n)
    # inferno default / cinema
    return _matplotlib_lut("inferno", n)


def _matplotlib_lut(name: str, n: int) -> NDArray[np.uint8]:
    try:
        import matplotlib.cm as cm

        cmap = cm.get_cmap(name, n)
        rgba = (cmap(np.linspace(0, 1, n)) * 255).astype(np.uint8)
        return rgba
    except Exception:
        return _build_gradient_lut(n, (0, 0, 0), (180, 50, 0), (255, 220, 100))


def _build_gradient_lut(
    n: int,
    c0: tuple[int, int, int],
    c1: tuple[int, int, int],
    c2: tuple[int, int, int],
) -> NDArray[np.uint8]:
    t = np.linspace(0, 1, n)
    mid = 0.5
    rgba = np.zeros((n, 4), dtype=np.uint8)
    for i, x in enumerate(t):
        if x < mid:
            u = x / mid
            r = int(c0[0] + u * (c1[0] - c0[0]))
            g = int(c0[1] + u * (c1[1] - c0[1]))
            b = int(c0[2] + u * (c1[2] - c0[2]))
        else:
            u = (x - mid) / (1 - mid)
            r = int(c1[0] + u * (c2[0] - c1[0]))
            g = int(c1[1] + u * (c2[1] - c1[1]))
            b = int(c1[2] + u * (c2[2] - c1[2]))
        rgba[i] = (r, g, b, 255)
    return rgba


def db_to_normalized(
    db: NDArray[np.float64],
    db_min: float,
    db_max: float,
    gamma: float = 1.0,
) -> NDArray[np.float64]:
    norm = (db - db_min) / max(db_max - db_min, 1e-6)
    norm = np.clip(norm, 0, 1)
    if gamma != 1.0:
        norm = np.power(norm, gamma)
    return norm
