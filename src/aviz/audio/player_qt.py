"""File playback via Qt Multimedia (used on Android)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from aviz.audio.decoder import AudioData, load_audio_file


class AudioPlayer:
    def __init__(self) -> None:
        self._audio: AudioData | None = None
        self._mono: np.ndarray | None = None
        self._player = QMediaPlayer()
        self._output = QAudioOutput()
        self._player.setAudioOutput(self._output)
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self.on_finished: Callable[[], None] | None = None
        self._finish_notified = False

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
        if not self._audio:
            return 0.0
        ms = self._player.position()
        return min(ms / 1000.0, self.duration)

    @property
    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def load(self, path: Path) -> AudioData:
        self.stop()
        self._audio = load_audio_file(path)
        self._set_mono(self._audio)
        self._player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self._finish_notified = False
        return self._audio

    def load_audio(self, audio: AudioData) -> None:
        self.stop()
        self._audio = audio
        self._set_mono(audio)
        self._player.setSource(QUrl.fromLocalFile(str(audio.path.resolve())))
        self._finish_notified = False

    def _set_mono(self, audio: AudioData) -> None:
        if audio.samples.ndim == 1:
            self._mono = audio.samples
        else:
            self._mono = audio.samples.mean(axis=1)
        self._player.setPosition(0)

    def play(self) -> None:
        if not self._audio:
            return
        self._finish_notified = False
        if self.position >= self.duration - 0.05 and self.duration > 0:
            self._player.setPosition(0)
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()
        self._player.setPosition(0)
        self._finish_notified = False

    def seek(self, seconds: float) -> None:
        if not self._audio:
            return
        was_playing = self.is_playing
        self._player.pause()
        ms = int(np.clip(seconds, 0, self.duration) * 1000)
        self._player.setPosition(ms)
        if was_playing:
            self._player.play()

    def toggle(self) -> None:
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def finalize_on_main_thread(self) -> None:
        self._player.stop()

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state != QMediaPlayer.PlaybackState.StoppedState:
            return
        if not self._audio or self._finish_notified:
            return
        if self.position < self.duration - 0.25:
            return
        self._finish_notified = True
        if self.on_finished:
            self.on_finished()
