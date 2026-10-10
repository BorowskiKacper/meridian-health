import base64

import httpx

# Clinical dictation. Scribe v2 Medical uses the same request as scribe_v2.
_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
_STT_MODEL = "scribe_v2_medical"
# Premade voice used for the short spoken read-back. Not a patient setting.
_TTS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
_TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{_TTS_VOICE_ID}"
_TTS_MODEL = "eleven_flash_v2_5"
_TIMEOUT_SECONDS = 60.0


def _api_key():
    import app.config as config

    key = getattr(config, "ELEVENLABS_API_KEY", "")
    if isinstance(key, str):
        return key.strip()
    return ""


class SpeechHook:
    def transcribe(self, audio):
        key = _api_key()
        if not key or not audio:
            return None
        try:
            response = httpx.post(
                _STT_URL,
                headers={"xi-api-key": key},
                data={"model_id": _STT_MODEL, "language_code": "eng"},
                files={
                    "file": ("dictation.audio", audio, "application/octet-stream")
                },
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return None
        text = payload.get("text") if isinstance(payload, dict) else None
        if isinstance(text, str) and text.strip():
            return text.strip()
        return None

    def synthesize(self, text):
        key = _api_key()
        if not key or not isinstance(text, str) or not text.strip():
            return None
        try:
            response = httpx.post(
                _TTS_URL,
                headers={"xi-api-key": key, "Accept": "audio/mpeg"},
                json={"text": text, "model_id": _TTS_MODEL},
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except Exception:
            return None
        if not response.content:
            return None
        return base64.b64encode(response.content).decode("ascii")
