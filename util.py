import io
import os
import sys
import time
import wave

import sounddevice


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def open_stream(audio_bytes):
    if type(audio_bytes) is bytes:
        audio_bytes = io.BytesIO(audio_bytes)
    with wave.open(audio_bytes, "rb") as wf:
        stream = sounddevice.RawOutputStream(samplerate=wf.getframerate(), channels=wf.getnchannels(), dtype="int16")
        stream.start()
        return stream


def play_audio(stream, audio_bytes):
    if type(audio_bytes) is bytes:
        audio_bytes = io.BytesIO(audio_bytes)
    with wave.open(audio_bytes, "rb") as wf:
        stream.write(wf.readframes(wf.getnframes()))


def play_audio_file(path):
    """
    Plays a WAV file on the default output device and blocks until playback
    finishes. Used for short confirmation sounds (e.g. Start/Stop feedback).

    This is feedback only - a missing or unreadable/unsupported file must
    never raise and never block the caller indefinitely, so any failure to
    read or parse the file is swallowed silently and simply results in no
    sound being played.
    """
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return

    try:
        with wave.open(io.BytesIO(data), "rb") as wf:
            duration = wf.getnframes() / float(wf.getframerate())

        stream = open_stream(data)
        play_audio(stream, data)
        time.sleep(duration + 0.05)
        stream.close()
    except Exception:
        pass


def play_beep():
    play_audio_file(str(resource_path("beep.wav")))


def initialise_audio():
    stream = sounddevice.RawOutputStream(samplerate=44100, channels=1, dtype="int16")
    stream.start()
    stream.close()