"""scipy on desktop; numpy fallbacks on Android (scipy often SIGSEGV in APK)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from aviz.runtime import is_android

if is_android():
    from numpy.fft import rfft, rfftfreq

    def get_window(name: str, N: int, fftbins: bool = True) -> NDArray[np.float64]:
        del fftbins
        if name in ("hann", "hanning"):
            return np.hanning(N).astype(np.float64)
        raise ValueError(f"Unsupported window on Android: {name}")

    def spectrogram(
        x: NDArray[np.float64],
        fs: float = 1.0,
        window: str = "hann",
        nperseg: int = 256,
        noverlap: int | None = None,
        mode: str = "magnitude",
    ) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
        del window, mode
        if noverlap is None:
            noverlap = nperseg // 2
        hop = nperseg - noverlap
        n = len(x)
        if n < nperseg:
            x = np.pad(x, (0, nperseg - n))
            n = nperseg
        n_frames = 1 + max(0, (n - nperseg) // hop)
        win = np.hanning(nperseg).astype(np.float64)
        cols: list[NDArray[np.float64]] = []
        for i in range(n_frames):
            start = i * hop
            seg = x[start : start + nperseg]
            if len(seg) < nperseg:
                seg = np.pad(seg, (0, nperseg - len(seg)))
            cols.append(np.abs(rfft(seg * win)))
        Sxx = np.column_stack(cols) if cols else np.zeros((nperseg // 2 + 1, 0))
        freqs = rfftfreq(nperseg, d=1.0 / fs)
        times = np.arange(Sxx.shape[1]) * hop / fs
        return freqs.astype(np.float64), times.astype(np.float64), Sxx.astype(np.float64)

else:
    from scipy.fft import rfft, rfftfreq
    from scipy.signal import get_window, spectrogram
