from __future__ import annotations

from bus.event_bus import EventBus
from bus.events import GameEndedEvent, InvalidMoveEvent, MoveMadeEvent, ScoreChangedEvent
from bus_handlers.protocols import SoundPlayer


class SoundHandler:
    """Plays a "move" sound whenever a move starts, a "capture" sound
    whenever a capture actually lands, an "illegal_move" sound whenever a
    player-facing rule violation is rejected, and a "game_over" sound once
    the game ends. Forwards to an injected SoundPlayer - has no idea what
    "playing a sound" actually involves, or what backend does it.

    MoveMadeEvent fires the instant a move is *requested*, before its
    real-time arrival is resolved - whether it captures anything is only
    known later, when GameEngine settles the arrival and publishes
    ScoreChangedEvent (see GameEngine._apply_events in game/engine.py). So
    the capture sound is driven by that event, not by guessing at a
    capture flag on MoveMadeEvent at request time.
    """

    def __init__(self, bus: EventBus, sound_player: SoundPlayer):
        self._sound_player = sound_player
        bus.subscribe(MoveMadeEvent, self._on_move_made)
        bus.subscribe(ScoreChangedEvent, self._on_score_changed)
        bus.subscribe(InvalidMoveEvent, self._on_invalid_move)
        bus.subscribe(GameEndedEvent, self._on_game_ended)

    def _on_move_made(self, event: MoveMadeEvent) -> None:
        self._sound_player.play("move")

    def _on_score_changed(self, event: ScoreChangedEvent) -> None:
        self._sound_player.play("capture")

    def _on_invalid_move(self, event: InvalidMoveEvent) -> None:
        self._sound_player.play("illegal_move")

    def _on_game_ended(self, event: GameEndedEvent) -> None:
        self._sound_player.play("game_over")
