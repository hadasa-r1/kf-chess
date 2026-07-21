"""Real SoundPlayer backed by the standard library.

There is no audio-playback dependency (or dependency file at all) in this
project yet, and the only multimedia dep already present is cv2. Rather
than add a third-party audio library, this uses `winsound` - bundled with
Python on Windows, the only platform this project targets - so playing a
placeholder sound effect costs zero new dependencies.
"""

from __future__ import annotations

import logging
import os

try:
    import winsound
except ImportError:  # pragma: no cover - non-Windows platforms
    winsound = None

logger = logging.getLogger(__name__)

DEFAULT_SOUND_PATHS = {
    "move": "assets/sounds/move.wav",
    "capture": "assets/sounds/capture.wav",
    "illegal_move": "assets/sounds/illegal_move.wav",
    "game_over": "assets/sounds/game_over.wav",
}


class AudioSoundPlayer:
    """SoundPlayer that plays short WAV files via winsound.

    Playback failures (unknown sound_id, missing file, no audio backend,
    a winsound error) are caught and logged, never raised - a broken sound
    effect must never crash the render loop.
    """

    def __init__(self, sound_paths=None):
        self._sound_paths = sound_paths if sound_paths is not None else DEFAULT_SOUND_PATHS

    def play(self, sound_id: str) -> None:
        path = self._sound_paths.get(sound_id)
        if path is None:
            logger.warning("AudioSoundPlayer: unknown sound_id %r", sound_id)
            return
        if winsound is None:
            logger.warning("AudioSoundPlayer: no audio backend available on this platform")
            return
        if not os.path.isfile(path):
            logger.warning("AudioSoundPlayer: sound file not found: %s", path)
            return
        try:
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            logger.exception("AudioSoundPlayer: failed to play %r (%s)", sound_id, path)
