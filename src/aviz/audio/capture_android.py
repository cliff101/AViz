"""Microphone capture on Android (python-for-android / jnius)."""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

from aviz.config import DEFAULT_BLOCK_SIZE, DEFAULT_SAMPLE_RATE


@dataclass
class LoopbackDevice:
    index: int
    name: str
    is_loopback: bool


def _request_mic_permission() -> None:
    try:
        from android.permissions import Permission, request_permissions  # type: ignore[import-untyped]

        request_permissions([Permission.RECORD_AUDIO])
    except Exception:
        pass


def list_loopback_devices() -> list[LoopbackDevice]:
    return [LoopbackDevice(index=0, name="Microphone", is_loopback=False)]


def get_default_loopback_device() -> LoopbackDevice | None:
    devs = list_loopback_devices()
    return devs[0] if devs else None


@dataclass
class LoopbackProbeResult:
    device: LoopbackDevice
    rms: float
    chunk_count: int

    @property
    def has_signal(self) -> bool:
        return self.chunk_count > 0 and self.rms > 0.001


def probe_loopback_devices(seconds: float = 1.5) -> list[LoopbackProbeResult]:
    results: list[LoopbackProbeResult] = []
    for dev in list_loopback_devices():
        cap = LoopbackCapture(device_index=dev.index)
        cap.start()
        time.sleep(0.15)
        chunks: list[np.ndarray] = []
        deadline = time.time() + seconds
        while time.time() < deadline:
            c = cap.read(timeout=0.1)
            if c is not None and len(c):
                chunks.append(c)
        cap.stop()
        if chunks:
            audio = np.concatenate(chunks)
            rms = float(np.sqrt(np.mean(audio**2)))
        else:
            rms = 0.0
        results.append(
            LoopbackProbeResult(device=dev, rms=rms, chunk_count=len(chunks))
        )
    return results


def best_loopback_probe(results: list[LoopbackProbeResult]) -> LoopbackProbeResult | None:
    if not results:
        return None
    return max(results, key=lambda r: r.rms)


class LoopbackCapture:
    """Captures microphone PCM into a thread-safe queue."""

    def __init__(
        self,
        device_index: int,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        block_size: int = DEFAULT_BLOCK_SIZE,
        on_chunk: Callable[[np.ndarray, float], None] | None = None,
    ) -> None:
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.on_chunk = on_chunk
        self._thread: threading.Thread | None = None
        self._running = False
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=32)

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        _request_mic_permission()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def read(self, timeout: float = 0.05) -> np.ndarray | None:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _run(self) -> None:
        try:
            from jnius import autoclass  # type: ignore[import-untyped]
        except ImportError:
            return

        AudioFormat = autoclass("android.media.AudioFormat")
        AudioRecord = autoclass("android.media.AudioRecord")
        MediaRecorder = autoclass("android.media.MediaRecorder")

        channel = AudioFormat.CHANNEL_IN_MONO
        encoding = AudioFormat.ENCODING_PCM_16BIT
        sr = int(self.sample_rate)
        min_buf = AudioRecord.getMinBufferSize(sr, channel, encoding)
        if min_buf <= 0:
            min_buf = self.block_size * 4
        buf_size = max(min_buf, self.block_size * 4)

        record = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            sr,
            channel,
            encoding,
            buf_size,
        )
        if record.getState() != AudioRecord.STATE_INITIALIZED:
            record.release()
            return

        record.startRecording()
        try:
            while self._running:
                buf = bytearray(buf_size)
                n = record.read(buf, 0, buf_size)
                if n <= 0:
                    continue
                arr = (
                    np.frombuffer(bytes(buf[:n]), dtype=np.int16)
                    .astype(np.float32)
                    / 32768.0
                )
                if len(arr) > self.block_size:
                    arr = arr[: self.block_size]
                if not self._queue.full():
                    self._queue.put(arr.copy())
                if self.on_chunk:
                    self.on_chunk(arr, float(sr))
        finally:
            record.stop()
            record.release()
