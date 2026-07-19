"""One-time generator for placeholder sound-effect WAV files.

These are synthesized sine tones, not real sound design - stand-ins so
SoundHandler/AudioSoundPlayer are wired end-to-end until proper, properly
licensed sound assets replace them. Uses only the standard library
(wave/array/math) - no audio-asset download, no extra dependency.

Run once from the repo root: `python scripts/generate_placeholder_sounds.py`
"""
import array
import math
import os
import wave

SAMPLE_RATE = 44100
AMPLITUDE = 12000  # headroom under int16 range (+-32767), avoids clipping
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "sounds")


def _tone(frequency_hz, duration_ms):
    n_samples = int(SAMPLE_RATE * duration_ms / 1000)
    return [
        int(AMPLITUDE * math.sin(2 * math.pi * frequency_hz * i / SAMPLE_RATE))
        for i in range(n_samples)
    ]


def _write_wav(path, samples):
    with wave.open(path, "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit signed PCM
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(array.array("h", samples).tobytes())


def generate():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    move_path = os.path.join(OUTPUT_DIR, "move.wav")
    _write_wav(move_path, _tone(440, 150))  # single short A4 tone

    # Two quick ascending tones - audibly distinct from the single move tone.
    capture_path = os.path.join(OUTPUT_DIR, "capture.wav")
    _write_wav(capture_path, _tone(660, 90) + _tone(880, 90))

    print(f"Wrote {move_path}")
    print(f"Wrote {capture_path}")

    # Two low, closely-spaced (dissonant) tones played together - a short,
    # clearly negative "buzz", distinct from move.wav/capture.wav.
    illegal_move_path = os.path.join(OUTPUT_DIR, "illegal_move.wav")
    buzz = [a + b for a, b in zip(_tone(180, 200), _tone(190, 200))]
    _write_wav(illegal_move_path, buzz)
    print(f"Wrote {illegal_move_path}")

    # A longer, descending multi-tone sequence - clearly signals "the game
    # has ended", distinct in both length and shape from the other sounds.
    game_over_path = os.path.join(OUTPUT_DIR, "game_over.wav")
    game_over = _tone(523, 200) + _tone(392, 200) + _tone(330, 200) + _tone(220, 400)
    _write_wav(game_over_path, game_over)
    print(f"Wrote {game_over_path}")


if __name__ == "__main__":
    generate()
