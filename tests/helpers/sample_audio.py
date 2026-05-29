"""Generate royalty-free synthetic audio for tests and manual QA."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 48000

# Note frequencies (Hz) for short "music" clips
NOTES = {
    "C4": 261.63,
    "D4": 293.66,
    "E4": 329.63,
    "F4": 349.23,
    "G4": 392.00,
    "A4": 440.00,
    "B4": 493.88,
    "C5": 523.25,
}


def _t(duration: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    return np.arange(int(duration * sr), dtype=np.float64) / sr


def sine_tone(freq: float, duration: float, amplitude: float = 0.35) -> np.ndarray:
    return amplitude * np.sin(2 * np.pi * freq * _t(duration))


def make_tone_440hz(duration: float = 1.5) -> np.ndarray:
    return sine_tone(440.0, duration)


def make_chord_major(duration: float = 2.0) -> np.ndarray:
    """C major chord: C4 + E4 + G4."""
    t = _t(duration)
    sig = sum(
        0.2 * np.sin(2 * np.pi * f * t) for f in (NOTES["C4"], NOTES["E4"], NOTES["G4"])
    )
    return np.clip(sig, -1, 1).astype(np.float64)


def make_frequency_sweep(duration: float = 2.5) -> np.ndarray:
    """Log sweep 200 Hz → 4000 Hz — strong spectrogram diagonal."""
    t = _t(duration)
    f0, f1 = 200.0, 4000.0
    phase = 2 * np.pi * f0 * duration / np.log(f1 / f0) * (np.exp(t / duration * np.log(f1 / f0)) - 1)
    return 0.4 * np.sin(phase)


def make_melody_arpeggio(duration: float = 3.0) -> np.ndarray:
    """Arpeggiated C major pentatonic — mini melody for playlist tests."""
    sequence = ["C4", "E4", "G4", "C5", "G4", "E4", "C4"]
    note_len = duration / len(sequence)
    parts = [sine_tone(NOTES[n], note_len * 0.95) for n in sequence]
    return np.concatenate(parts)


def make_stereo_pan(duration: float = 1.0) -> np.ndarray:
    """Stereo: tone pans left → right."""
    t = _t(duration)
    mono = 0.3 * np.sin(2 * np.pi * NOTES["A4"] * t)
    pan = np.linspace(-1, 1, len(t))
    left = mono * np.clip(1 - pan, 0, 1)
    right = mono * np.clip(1 + pan, 0, 1)
    return np.column_stack([left, right]).astype(np.float64)


def make_mixed_bands(duration: float = 2.0) -> np.ndarray:
    """Bass + mid + treble for band-meter / multi-peak tests."""
    t = _t(duration)
    bass = 0.25 * np.sin(2 * np.pi * 80 * t)
    mid = 0.2 * np.sin(2 * np.pi * 1000 * t)
    treble = 0.15 * np.sin(2 * np.pi * 8000 * t)
    return np.clip(bass + mid + treble, -1, 1)


SAMPLE_SPECS: dict[str, tuple[Callable[[], np.ndarray], None]] = {
    "tone_440hz.wav": (make_tone_440hz, None),
    "chord_major.wav": (make_chord_major, None),
    "sweep_log.wav": (make_frequency_sweep, None),
    "melody_arpeggio.wav": (make_melody_arpeggio, None),
    "stereo_pan.wav": (make_stereo_pan, None),
    "mixed_bands.wav": (make_mixed_bands, None),
}


def write_sample(path: Path, name: str) -> Path:
    factory, _ = SAMPLE_SPECS[name]
    data = factory()
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), data, SAMPLE_RATE, subtype="PCM_24")
    return path


def generate_all_samples(output_dir: Path) -> list[Path]:
    output_dir = Path(output_dir)
    written: list[Path] = []
    for name in SAMPLE_SPECS:
        p = output_dir / name
        write_sample(p, name)
        written.append(p)
    return written


def list_sample_paths(samples_dir: Path) -> dict[str, Path]:
    samples_dir = Path(samples_dir)
    return {name: samples_dir / name for name in SAMPLE_SPECS if (samples_dir / name).exists()}
