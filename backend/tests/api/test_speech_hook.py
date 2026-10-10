import base64
import socket

import httpx

from app.speech.hook import SpeechHook, _STT_MODEL, _TTS_MODEL, _TTS_URL, _TTS_VOICE_ID
from api_support import REPO_ROOT


def test_speech_hook_returns_none_without_a_network_call(monkeypatch):
    monkeypatch.setattr("app.config.ELEVENLABS_API_KEY", "")

    def create_connection(*args, **kwargs):
        raise AssertionError("socket.create_connection was called")

    monkeypatch.setattr(socket, "create_connection", create_connection)
    hook = SpeechHook()
    assert hook.transcribe(b"abc") is None
    assert hook.synthesize("hello") is None
    assert hook.transcribe(b"") is None
    assert hook.synthesize("   ") is None


def test_speech_hook_calls_elevenlabs_when_a_key_is_set(monkeypatch):
    monkeypatch.setattr("app.config.ELEVENLABS_API_KEY", "test-key")
    seen = []

    class Response:
        def __init__(self, payload=None, content=b""):
            self._payload = payload
            self.content = content

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def post(url, **kwargs):
        seen.append((url, kwargs))
        if url.endswith("/speech-to-text"):
            return Response({"text": "  Mark hypertension controlled.  "})
        return Response(content=b"mp3-bytes")

    monkeypatch.setattr("app.speech.hook.httpx.post", post)

    assert SpeechHook().transcribe(b"abc") == "Mark hypertension controlled."
    assert SpeechHook().synthesize("I will propose a chart update.") == base64.b64encode(
        b"mp3-bytes"
    ).decode("ascii")

    stt_url, stt_kwargs = seen[0]
    assert stt_url == "https://api.elevenlabs.io/v1/speech-to-text"
    assert stt_kwargs["headers"]["xi-api-key"] == "test-key"
    assert stt_kwargs["data"]["model_id"] == _STT_MODEL
    assert stt_kwargs["files"]["file"][1] == b"abc"
    tts_url, tts_kwargs = seen[1]
    assert tts_url == _TTS_URL
    assert _TTS_VOICE_ID in tts_url
    assert tts_kwargs["json"] == {
        "text": "I will propose a chart update.",
        "model_id": _TTS_MODEL,
    }
    assert tts_kwargs["headers"]["Accept"] == "audio/mpeg"


def test_speech_hook_returns_none_when_elevenlabs_fails(monkeypatch):
    monkeypatch.setattr("app.config.ELEVENLABS_API_KEY", "test-key")

    def post(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr("app.speech.hook.httpx.post", post)
    assert SpeechHook().transcribe(b"abc") is None
    assert SpeechHook().synthesize("hello") is None


def test_api_source_boundaries():
    api = REPO_ROOT / "backend" / "app" / "api"
    for path in api.rglob("*"):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        assert b"sqlalchemy" not in raw
        assert b"app.db" not in raw

    speech = REPO_ROOT / "backend" / "app" / "speech"
    modules = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in speech.rglob("*.py")
        if path.name != "__init__.py"
    )
    assert modules == ["backend/app/speech/hook.py"]
    assert not (REPO_ROOT / "web").is_dir()
