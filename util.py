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


def play_beep():
    with open(str(resource_path("beep.wav")), "rb") as f:
        data = f.read()

        stream = open_stream(data)
        play_audio(stream, data)
        time.sleep(0.5)
        stream.close()


def initialise_audio():
    stream = sounddevice.RawOutputStream(samplerate=44100, channels=1, dtype="int16")
    stream.start()
    stream.close()