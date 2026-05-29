"""File playback with sounddevice (desktop)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd

from aviz.audio.decoder import AudioData, load_audio_file


class AudioPlayer:
    def __init__(self) -> None:
        self._audio: AudioData | None = None
        self._mono: np.ndarray | None = None
        self._position = 0
        self._playing = False
        self._stream: sd.OutputStream | None = None
        self._lock = threading.Lock()
        self._start_position = 0
        self._frames_delivered = 0
        self._finish_notified = False
        self.on_finished: Callable[[], None] | None = None

    @property
    def audio(self) -> AudioData | None:
        return self._audio

    @property
    def mono(self) -> np.ndarray | None:
        return self._mono

    @property
    def duration(self) -> float:
        return self._audio.duration if self._audio else 0.0

    @property
    def position(self) -> float:
        with self._lock:
            if not self._audio:
                return 0.0
            sr = self._audio.sample_rate
            if self._playing:
                samples = self._start_position + self._frames_delivered
                return min(samples / sr, self.duration)
            return self._position / sr

    @property
    def is_playing(self) -> bool:
        return self._playing

    def load(self, path: Path) -> AudioData:
        self.stop()
        self._audio = load_audio_file(path)
        self._set_mono(self._audio)
        return self._audio

    def load_audio(self, audio: AudioData) -> None:
        self.stop()
        self._audio = audio
        self._set_mono(audio)

    def _set_mono(self, audio: AudioData) -> None:
        if audio.samples.ndim == 1:
            self._mono = audio.samples
        else:
            self._mono = audio.samples.mean(axis=1)
        self._position = 0

    def play(self) -> None:
        if not self._audio or self._mono is None:
            return
        self._close_stream()
        mono_len = len(self._mono)
        with self._lock:
            if mono_len and self._position >= mono_len - 1:
                self._position = 0
            self._playing = True
            self._start_position = self._position
            self._frames_delivered = 0
            self._finish_notified = False

        def callback(outdata, frames, time_info, status) -> None:  # noqa: ARG001
            with self._lock:
                if not self._playing or self._mono is None or self._audio is None:
                    outdata.fill(0)
                    raise sd.CallbackStop()
                pos = self._start_position + self._frames_delivered

            end = pos + frames
            mono = self._mono
            if pos >= len(mono):
                outdata.fill(0)
                self._mark_finished()
                raise sd.CallbackStop()

            chunk = mono[pos:end]
            n = len(chunk)
            outdata[:n, 0] = chunk
            if n < frames:
                outdata[n:, 0] = 0
            if outdata.shape[1] > 1:
                outdata[:, 1] = outdata[:, 0]

            with self._lock:
                self._frames_delivered += n
                self._position = self._start_position + self._frames_delivered
                at_end = n < frames

            if at_end:
                self._mark_finished()
                raise sd.CallbackStop()

        channels = max(1, self._audio.channels)
        self._stream = sd.OutputStream(
            samplerate=self._audio.sample_rate,
            channels=channels,
            callback=callback,
            blocksize=1024,
        )
        self._stream.start()

    def _mark_finished(self) -> None:
        with self._lock:
            self._playing = False
            if self._mono is not None:
                self._position = len(self._mono)
            if self._finish_notified:
                return
            self._finish_notified = True
        if self.on_finished:
            self.on_finished()

    def finalize_on_main_thread(self) -> None:
        with self._lock:
            self._playing = False
        self._close_stream()

    def pause(self) -> None:
        with self._lock:
            if self._playing and self._audio:
                self._position = self._start_position + self._frames_delivered
            self._playing = False
        self._close_stream()

    def stop(self) -> None:
        self.pause()
        self._position = 0

    def seek(self, seconds: float) -> None:
        if not self._audio:
            return
        was_playing = self._playing
        self.pause()
        self._position = int(
            np.clip(seconds, 0, self.duration) * self._audio.sample_rate
        )
        if was_playing:
            self.play()

    def toggle(self) -> None:
        if self._playing:
            self.pause()
        else:
            self.play()

    def _close_stream(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is not None:
            stream.stop()
            stream.close()
