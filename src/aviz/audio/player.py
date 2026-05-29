"""File playback — sounddevice on desktop, Qt Multimedia on Android."""

from __future__ import annotations

from aviz.runtime import is_android

if is_android():
    from aviz.audio.player_qt import AudioPlayer  # noqa: F401
else:
    from aviz.audio.player_sd import AudioPlayer  # noqa: F401
