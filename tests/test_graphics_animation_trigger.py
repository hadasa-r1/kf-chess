import logging

from bus_handlers.graphics_animation_trigger import GraphicsAnimationTrigger


def test_unknown_animation_id_is_logged_and_does_not_raise(caplog):
    trigger = GraphicsAnimationTrigger()

    with caplog.at_level(logging.INFO):
        trigger.trigger("not_a_real_animation")  # must not raise

    assert "not_a_real_animation" in caplog.text


def test_known_animation_ids_do_not_raise():
    trigger = GraphicsAnimationTrigger()

    trigger.trigger("game_start")
    trigger.trigger("game_end")
