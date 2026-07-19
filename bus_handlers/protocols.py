from __future__ import annotations

from typing import Protocol


class SoundPlayer(Protocol):
    """Whatever plays a sound effect - real backend TBD."""

    def play(self, sound_id: str) -> None: ...


class AnimationTrigger(Protocol):
    """Whatever plays an animation - real backend TBD."""

    def trigger(self, animation_id: str) -> None: ...


class NullSoundPlayer:
    """Trivial SoundPlayer that records calls instead of playing audio."""

    def __init__(self):
        self.played: list[str] = []

    def play(self, sound_id: str) -> None:
        self.played.append(sound_id)


class NullAnimationTrigger:
    """Trivial AnimationTrigger that records calls instead of animating."""

    def __init__(self):
        self.triggered: list[str] = []

    def trigger(self, animation_id: str) -> None:
        self.triggered.append(animation_id)
