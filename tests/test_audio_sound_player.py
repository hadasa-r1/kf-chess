import logging

import bus_handlers.audio_sound_player as audio_sound_player_module
from bus_handlers.audio_sound_player import AudioSoundPlayer


def test_unknown_sound_id_is_logged_and_does_not_raise(caplog):
    player = AudioSoundPlayer(sound_paths={"move": "assets/sounds/move.wav"})

    with caplog.at_level(logging.WARNING):
        player.play("nonexistent")  # must not raise

    assert "nonexistent" in caplog.text


def test_missing_sound_file_is_logged_and_does_not_raise(caplog, tmp_path):
    missing_path = str(tmp_path / "does_not_exist.wav")
    player = AudioSoundPlayer(sound_paths={"move": missing_path})

    with caplog.at_level(logging.WARNING):
        player.play("move")  # must not raise

    assert missing_path in caplog.text


def test_missing_audio_backend_is_logged_and_does_not_raise(monkeypatch, caplog, tmp_path):
    existing_file = tmp_path / "move.wav"
    existing_file.write_bytes(b"")
    monkeypatch.setattr(audio_sound_player_module, "winsound", None)

    player = AudioSoundPlayer(sound_paths={"move": str(existing_file)})
    with caplog.at_level(logging.WARNING):
        player.play("move")  # must not raise

    assert "backend" in caplog.text.lower()


def test_playback_error_is_logged_and_does_not_raise(monkeypatch, caplog, tmp_path):
    existing_file = tmp_path / "move.wav"
    existing_file.write_bytes(b"")

    class _ExplodingWinsound:
        SND_FILENAME = 0
        SND_ASYNC = 0

        @staticmethod
        def PlaySound(path, flags):
            raise OSError("boom")

    monkeypatch.setattr(audio_sound_player_module, "winsound", _ExplodingWinsound)

    player = AudioSoundPlayer(sound_paths={"move": str(existing_file)})
    with caplog.at_level(logging.ERROR):
        player.play("move")  # must not raise

    assert "failed to play" in caplog.text.lower()
