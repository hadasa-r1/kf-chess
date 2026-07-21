from bus.event_bus import EventBus
from bus.events import GameEndedEvent, InvalidMoveEvent, MoveMadeEvent, ScoreChangedEvent
from bus_handlers.protocols import NullSoundPlayer
from bus_handlers.sound_handler import SoundHandler


def test_move_made_event_triggers_exactly_one_sound_call():
    bus = EventBus()
    sound_player = NullSoundPlayer()
    SoundHandler(bus, sound_player)

    bus.publish(MoveMadeEvent(color="w", piece="wR", start=(0, 0), end=(0, 1), timestamp=0))

    assert sound_player.played == ["move"]


def test_multiple_moves_trigger_one_sound_call_each():
    bus = EventBus()
    sound_player = NullSoundPlayer()
    SoundHandler(bus, sound_player)

    bus.publish(MoveMadeEvent(color="w", piece="wR", start=(0, 0), end=(0, 1), timestamp=0))
    bus.publish(MoveMadeEvent(color="b", piece="bR", start=(7, 0), end=(7, 1), timestamp=1))

    assert sound_player.played == ["move", "move"]


def test_score_changed_event_triggers_exactly_one_capture_sound_call():
    bus = EventBus()
    sound_player = NullSoundPlayer()
    SoundHandler(bus, sound_player)

    bus.publish(ScoreChangedEvent(player="w", new_score=1))

    assert sound_player.played == ["capture"]


def test_move_then_capture_plays_both_sounds_in_order():
    bus = EventBus()
    sound_player = NullSoundPlayer()
    SoundHandler(bus, sound_player)

    bus.publish(MoveMadeEvent(color="w", piece="wR", start=(0, 0), end=(0, 2), timestamp=0))
    bus.publish(ScoreChangedEvent(player="w", new_score=1))

    assert sound_player.played == ["move", "capture"]


def test_invalid_move_event_triggers_exactly_one_illegal_move_sound_call():
    bus = EventBus()
    sound_player = NullSoundPlayer()
    SoundHandler(bus, sound_player)

    bus.publish(InvalidMoveEvent(reason="illegal_piece_move", start=(0, 0), end=(0, 1)))

    assert sound_player.played == ["illegal_move"]


def test_game_ended_event_triggers_exactly_one_game_over_sound_call():
    bus = EventBus()
    sound_player = NullSoundPlayer()
    SoundHandler(bus, sound_player)

    bus.publish(GameEndedEvent(winner="w", reason="captured_K"))

    assert sound_player.played == ["game_over"]
