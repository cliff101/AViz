"""WASAPI loopback capture on Windows."""

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


def list_loopback_devices() -> list[LoopbackDevice]:
    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        return []
    pa = pyaudio.PyAudio()
    devices: list[LoopbackDevice] = []
    try:
        for i in range(pa.get_device_count()):
            dev = pa.get_device_info_by_index(i)
            if dev.get("isLoopbackDevice"):
                devices.append(
                    LoopbackDevice(index=i, name=dev["name"], is_loopback=True)
                )
        if not devices:
            try:
                for dev in pa.get_loopback_device_info_generator():
                    devices.append(
                        LoopbackDevice(
                            index=dev["index"],
                            name=dev["name"] + " [Loopback]",
                            is_loopback=True,
                        )
                    )
            except Exception:
                pass
    finally:
        pa.terminate()
    return devices


def get_default_loopback_device() -> LoopbackDevice | None:
    """Loopback device matching the current WASAPI default playback output."""
    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        return None
    pa = pyaudio.PyAudio()
    try:
        wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        out_idx = wasapi.get("defaultOutputDevice", -1)
        if out_idx < 0:
            return None
        out_name = pa.get_device_info_by_index(out_idx).get("name", "")
        loopbacks = list_loopback_devices()
        if not loopbacks:
            return None
        for lb in loopbacks:
            base = lb.name.replace(" [Loopback]", "").strip()
            if out_name in lb.name or base in out_name or out_name in base:
                return lb
        candidate = out_idx + 1
        for lb in loopbacks:
            if lb.index == candidate:
                return lb
        return loopbacks[0]
    except Exception:
        return None
    finally:
        pa.terminate()


@dataclass
class LoopbackProbeResult:
    device: LoopbackDevice
    rms: float
    chunk_count: int

    @property
    def has_signal(self) -> bool:
        return self.chunk_count > 0 and self.rms > 0.001


def probe_loopback_devices(seconds: float = 1.5) -> list[LoopbackProbeResult]:
    """Measure RMS on each loopback device (call from a background thread)."""
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
    """Captures audio from a WASAPI loopback device into a thread-safe queue."""

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
            import pyaudiowpatch as pyaudio
        except ImportError:
            return
        pa = pyaudio.PyAudio()
        stream = None
        try:
            dev = pa.get_device_info_by_index(self.device_index)
            sr = int(dev["defaultSampleRate"])
            channels = int(dev["maxInputChannels"]) or 2
            stream = pa.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=sr,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.block_size,
            )
            self.sample_rate = sr
            while self._running:
                raw = stream.read(self.block_size, exception_on_overflow=False)
                arr = np.frombuffer(raw, dtype=np.float32)
                if channels > 1:
                    arr = arr.reshape(-1, channels).mean(axis=1)
                if not self._queue.full():
                    self._queue.put(arr.copy())
                if self.on_chunk:
                    self.on_chunk(arr, sr)
        except Exception:
            pass
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            pa.terminate()
