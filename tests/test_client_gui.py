from bus.event_bus import EventBus
from bus_handlers.animation_trigger_handler import AnimationTriggerHandler
from bus_handlers.audio_sound_player import AudioSoundPlayer
from bus_handlers.graphics_animation_trigger import GraphicsAnimationTrigger
from bus_handlers.sound_handler import SoundHandler
from client_gui import _ConnectionState


def test_sound_and_animation_handlers_construct_on_a_real_local_bus():
    # Mirrors main_gui.py's own composition (see tests/test_main_gui.py's
    # test_build_bus_handlers_constructs_all_four_handlers) - proves
    # client_gui.py can wire the exact same, unmodified handler classes
    # onto its local, client-side EventBus without error.
    bus = EventBus()

    sound_handler = SoundHandler(bus, AudioSoundPlayer())
    animation_handler = AnimationTriggerHandler(bus, GraphicsAnimationTrigger())

    assert isinstance(sound_handler, SoundHandler)
    assert isinstance(animation_handler, AnimationTriggerHandler)


def test_connection_state_room_fields_default_to_unset():
    state = _ConnectionState()

    assert state.room_id is None
    assert state.room_not_found is False


def test_on_room_created_sets_room_id():
    state = _ConnectionState()

    state.on_room_created("abcd1234")

    assert state.room_id == "abcd1234"


def test_on_room_joined_sets_room_id():
    state = _ConnectionState()

    state.on_room_joined("abcd1234")

    assert state.room_id == "abcd1234"


def test_on_room_not_found_sets_the_flag():
    state = _ConnectionState()

    state.on_room_not_found()

    assert state.room_not_found is True


def test_is_viewer_defaults_to_false():
    state = _ConnectionState()

    assert state.is_viewer is False


def test_on_viewer_assigned_sets_the_flag():
    state = _ConnectionState()

    state.on_viewer_assigned()

    assert state.is_viewer is True
