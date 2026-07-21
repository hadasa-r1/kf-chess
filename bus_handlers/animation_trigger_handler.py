from __future__ import annotations

from bus.event_bus import EventBus
from bus.events import GameEndedEvent, GameStartedEvent
from bus_handlers.protocols import AnimationTrigger


class AnimationTriggerHandler:
    """Triggers start/end animations whenever GameStartedEvent or
    GameEndedEvent is published. Forwards to an injected AnimationTrigger -
    has no idea what "playing an animation" actually involves, or what
    backend does it.
    """

    def __init__(self, bus: EventBus, animation_trigger: AnimationTrigger):
        self._animation_trigger = animation_trigger
        bus.subscribe(GameStartedEvent, self._on_game_started)
        bus.subscribe(GameEndedEvent, self._on_game_ended)

    def _on_game_started(self, event: GameStartedEvent) -> None:
        self._animation_trigger.trigger("game_start")

    def _on_game_ended(self, event: GameEndedEvent) -> None:
        self._animation_trigger.trigger("game_end")
