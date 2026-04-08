import os
import tempfile
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = None


def _resolve_groq_api_key() -> str:
    direct = (os.getenv("GROQ_API_KEY") or "").strip()
    if direct:
        return direct

    legacy = (os.getenv("GROQ_TOKEN") or "").strip()
    if legacy.startswith("GROQ_API_KEY="):
        legacy = legacy.split("=", 1)[1].strip()
    return legacy

def get_client():
    global _client
    if _client is None:
        api_key = _resolve_groq_api_key()
        if not api_key:
            raise RuntimeError(
                "Groq API key is missing. Set GROQ_API_KEY or legacy GROQ_TOKEN in the environment."
            )
        _client = Groq(api_key=api_key)
    return _client


def transcribe_bytes(audio_bytes: bytes, ext: str = "ogg") -> str:
    """Транскрибирует аудио через Groq Whisper. Быстро, бесплатно."""
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        client = get_client()
        with open(tmp_path, "rb") as audio_file:
            result = client.audio.transcriptions.create(
                file=(f"audio.{ext}", audio_file),
                model="whisper-large-v3-turbo",
                response_format="text",
            )
        return result.strip() if isinstance(result, str) else result.text.strip()
    finally:
        os.unlink(tmp_path)
