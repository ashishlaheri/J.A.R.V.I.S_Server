"""Server-side TTS engine using edge-tts — generates MP3 audio bytes."""

import edge_tts
import io
from config import settings


async def generate_speech(text: str) -> bytes:
    """Generate MP3 audio bytes from text using Edge-TTS.
    Returns the raw MP3 bytes ready to send to the client.
    """
    communicate = edge_tts.Communicate(text, voice=settings.TTS_VOICE)
    buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    return buffer.getvalue()
