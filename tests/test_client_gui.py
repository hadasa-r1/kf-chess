from bus.event_bus import EventBus
from bus_handlers.animation_trigger_handler import AnimationTriggerHandler
from bus_handlers.audio_sound_player import AudioSoundPlayer
from bus_handlers.graphics_animation_trigger import GraphicsAnimationTrigger
from bus_handlers.sound_handler import SoundHandler


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
