"""Decode audio files (and extract audio from video via ffmpeg)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from numpy.typing import NDArray

from aviz.config import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS


@dataclass
class AudioData:
    samples: NDArray[np.float64]
    sample_rate: int
    channels: int
    path: Path
    duration: float
    subtype: str = ""

    @property
    def display_name(self) -> str:
        return self.path.name


def load_audio_file(path: Path) -> AudioData:
    path = Path(path).resolve()
    suffix = path.suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return _load_via_ffmpeg(path)
    if suffix not in AUDIO_EXTENSIONS and suffix:
        pass
    try:
        return _load_soundfile(path)
    except Exception:
        if suffix == ".wav":
            return _load_wav_stdlib(path)
        raise


def _load_wav_stdlib(path: Path) -> AudioData:
    import wave

    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sr = wf.getframerate()
        width = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())
    if width == 2:
        arr = np.frombuffer(frames, dtype=np.int16).astype(np.float64) / 32768.0
    elif width == 4:
        arr = np.frombuffer(frames, dtype=np.int32).astype(np.float64) / 2147483648.0
    else:
        raise RuntimeError(f"Unsupported WAV sample width in {path.name}")
    if channels > 1:
        arr = arr.reshape(-1, channels)
    else:
        arr = arr.reshape(-1, 1)
    duration = len(arr) / sr
    return AudioData(
        samples=arr,
        sample_rate=sr,
        channels=channels,
        path=path,
        duration=duration,
        subtype="wav",
    )


def _load_soundfile(path: Path) -> AudioData:
    data, sr = sf.read(str(path), always_2d=True, dtype="float64")
    channels = data.shape[1]
    samples = data
    duration = len(samples) / sr
    info = sf.info(str(path))
    return AudioData(
        samples=samples,
        sample_rate=sr,
        channels=channels,
        path=path,
        duration=duration,
        subtype=getattr(info, "subtype", "") or "",
    )


def _load_via_ffmpeg(path: Path) -> AudioData:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install ffmpeg to open video files."
        )
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(path),
                "-vn",
                "-acodec",
                "pcm_f32le",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(tmp_path),
            ],
            check=True,
            capture_output=True,
        )
        audio = _load_soundfile(tmp_path)
        return AudioData(
            samples=audio.samples,
            sample_rate=audio.sample_rate,
            channels=audio.channels,
            path=path,
            duration=audio.duration,
            subtype="video→wav",
        )
    finally:
        tmp_path.unlink(missing_ok=True)
