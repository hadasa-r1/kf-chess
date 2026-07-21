from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    """Base class for every event carried on the EventBus."""


@dataclass(frozen=True)
class MoveMadeEvent(Event):
    """Mirrors game.move_history.MoveRecord's fields, so GameEngine can
    build one directly from the other."""

    color: str
    piece: str
    start: tuple
    end: tuple
    timestamp: int


@dataclass(frozen=True)
class ScoreChangedEvent(Event):
    player: str
    new_score: int


@dataclass(frozen=True)
class GameStartedEvent(Event):
    white_player: str
    black_player: str


@dataclass(frozen=True)
class GameEndedEvent(Event):
    winner: str
    reason: str


@dataclass(frozen=True)
class InvalidMoveEvent(Event):
    """A player-facing rule violation - not an internal busy/timing state
    like GAME_OVER/ON_COOLDOWN/BUSY_SOURCE (see GameEngine.request_move)."""

    reason: str
    start: tuple
    end: tuple
