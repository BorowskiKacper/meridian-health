import base64
from functools import lru_cache

import httpx

from app import config
from app.integrations import IntegrationError

_ROOT = "https://api.elevenlabs.io/v1"


def _request(method, path, **kwargs):
    if not config.ELEVENLABS_API_KEY:
        raise IntegrationError("ElevenLabs", "Voice services are not configured on the server.")
    try:
        response = httpx.request(method, _ROOT + path, headers={"xi-api-key": config.ELEVENLABS_API_KEY}, timeout=60, **kwargs)
        response.raise_for_status()
        return response
    except Exception:
        raise IntegrationError("ElevenLabs", "The voice service could not complete this request. Try again.") from None


@lru_cache(maxsize=1)
def _voice(key):
    voices = _request("GET", "/voices").json().get("voices", [])
    if not voices:
        raise IntegrationError("ElevenLabs", "No voice is available for this ElevenLabs account.")
    return voices[0]["voice_id"]


def _mime(audio):
    if audio.startswith(b"\x1aE\xdf\xa3"):
        return "audio/webm"
    if audio.startswith(b"OggS"):
        return "audio/ogg"
    if audio.startswith(b"RIFF"):
        return "audio/wav"
    # Phone recordings are M4A, an MP4 container whose type sits after the size field.
    if len(audio) >= 8 and audio[4:8] == b"ftyp":
        return "audio/mp4"
    return "audio/mpeg"


class SpeechHook:
    def transcribe(self, audio):
        if not audio or len(audio) > 20 * 1024 * 1024:
            raise IntegrationError("ElevenLabs", "Provide a nonempty recording under 20 MB.")
        response = _request(
            "POST",
            "/speech-to-text",
            data={"model_id": "scribe_v2", "tag_audio_events": "false"},
            files={"file": ("dictation", audio, _mime(audio))},
        )
        text = response.json().get("text", "").strip()
        if not text:
            raise IntegrationError("ElevenLabs", "No speech was recognized. Record again or type your request.")
        return text

    def synthesize(self, text):
        if not isinstance(text, str) or not text.strip():
            raise IntegrationError("ElevenLabs", "There is no response to speak.")
        voice = config.ELEVENLABS_VOICE_ID or _voice(config.ELEVENLABS_API_KEY)
        response = _request("POST", f"/text-to-speech/{voice}", json={"text": text, "model_id": "eleven_flash_v2_5"})
        return base64.b64encode(response.content).decode("ascii")
