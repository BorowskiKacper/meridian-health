import base64

import httpx

from app import config

_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"


class SpeechHook:
    def transcribe(self, audio):
        if not config.ELEVENLABS_API_KEY or not audio:
            return None
        try:
            response = httpx.post(
                _STT_URL,
                headers={"xi-api-key": config.ELEVENLABS_API_KEY},
                files={"file": ("audio", audio)},
                data={
                    "model_id": config.ELEVENLABS_STT_MODEL,
                    "language_code": "eng",
                },
                timeout=60.0,
            )
        except httpx.HTTPError:
            return None
        if response.status_code < 200 or response.status_code >= 300:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str) or not text.strip():
            return None
        return text.strip()

    def synthesize(self, text):
        if not config.ELEVENLABS_API_KEY or not isinstance(text, str) or not text:
            return None
        url = (
            "https://api.elevenlabs.io/v1/text-to-speech/"
            f"{config.ELEVENLABS_VOICE_ID}?output_format={config.ELEVENLABS_TTS_FORMAT}"
        )
        try:
            response = httpx.post(
                url,
                headers={
                    "xi-api-key": config.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                },
                json={"text": text, "model_id": config.ELEVENLABS_TTS_MODEL},
                timeout=30.0,
            )
        except httpx.HTTPError:
            return None
        if response.status_code < 200 or response.status_code >= 300:
            return None
        if not response.content:
            return None
        return base64.b64encode(response.content).decode("ascii")
