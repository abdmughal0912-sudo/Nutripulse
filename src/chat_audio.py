from __future__ import annotations

import base64
import io
import math
import struct
import wave
from functools import lru_cache


@lru_cache(maxsize=3)
def message_sound_data_uri(kind: str = "exchange") -> str:
    """Create a short, dependency-free WAV chime for optional chat feedback."""
    sample_rate = 16_000
    sequences = {
        "send": [(659.25, 0.10), (783.99, 0.12)],
        "receive": [(783.99, 0.10), (987.77, 0.15)],
        "exchange": [(659.25, 0.08), (783.99, 0.09), (0.0, 0.05), (783.99, 0.09), (987.77, 0.14)],
    }
    notes = sequences.get(kind, sequences["exchange"])
    frames = bytearray()
    for frequency, duration in notes:
        count = max(1, int(sample_rate * duration))
        for index in range(count):
            if frequency <= 0:
                sample = 0
            else:
                position = index / count
                envelope = min(1.0, position / 0.08) * max(0.0, (1.0 - position) / 0.24)
                sample = int(32767 * 0.16 * envelope * math.sin(2 * math.pi * frequency * index / sample_rate))
            frames.extend(struct.pack("<h", sample))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(bytes(frames))
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:audio/wav;base64,{encoded}"


def message_sound_html(kind: str = "exchange") -> str:
    """Return an invisible autoplay element; the user controls whether it is rendered."""
    return (
        '<audio autoplay preload="auto" aria-hidden="true" style="display:none">'
        f'<source src="{message_sound_data_uri(kind)}" type="audio/wav">'
        "</audio>"
    )
