from bus.event_bus import EventBus
from bus.events import GameEndedEvent, GameStartedEvent
from bus_handlers.animation_trigger_handler import AnimationTriggerHandler
from bus_handlers.protocols import NullAnimationTrigger


def test_game_started_event_triggers_exactly_one_start_animation():
    bus = EventBus()
    animation_trigger = NullAnimationTrigger()
    AnimationTriggerHandler(bus, animation_trigger)

    bus.publish(GameStartedEvent(white_player="w", black_player="b"))

    assert animation_trigger.triggered == ["game_start"]


def test_game_ended_event_triggers_exactly_one_end_animation():
    bus = EventBus()
    animation_trigger = NullAnimationTrigger()
    AnimationTriggerHandler(bus, animation_trigger)

    bus.publish(GameEndedEvent(winner="w", reason="captured_K"))

    assert animation_trigger.triggered == ["game_end"]


def test_both_events_trigger_their_own_animation_independently():
    bus = EventBus()
    animation_trigger = NullAnimationTrigger()
    AnimationTriggerHandler(bus, animation_trigger)

    bus.publish(GameStartedEvent(white_player="w", black_player="b"))
    bus.publish(GameEndedEvent(winner="w", reason="captured_K"))

    assert animation_trigger.triggered == ["game_start", "game_end"]
