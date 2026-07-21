import main_gui
from bus.event_bus import EventBus
from bus_handlers.animation_trigger_handler import AnimationTriggerHandler
from bus_handlers.move_log_display_state import MoveLogDisplayState
from bus_handlers.score_display_state import ScoreDisplayState
from bus_handlers.sound_handler import SoundHandler


def test_main_builds_and_launches_the_gui(monkeypatch):
    calls = []
    monkeypatch.setattr(
        main_gui, "_run_loop",
        lambda engine, controller, renderer, score_state, move_log_state:
            calls.append((engine, controller, renderer, score_state, move_log_state)),
    )
    main_gui.main()
    assert len(calls) == 1
    engine, controller, renderer, score_state, move_log_state = calls[0]
    assert engine is not None and controller is not None and renderer is not None
    assert isinstance(score_state, ScoreDisplayState)
    assert isinstance(move_log_state, MoveLogDisplayState)


def test_build_bus_handlers_constructs_all_four_handlers():
    bus = EventBus()
    score_state, move_log_state, sound_handler, animation_handler = main_gui._build_bus_handlers(bus)

    assert isinstance(score_state, ScoreDisplayState)
    assert isinstance(move_log_state, MoveLogDisplayState)
    assert isinstance(sound_handler, SoundHandler)
    assert isinstance(animation_handler, AnimationTriggerHandler)
