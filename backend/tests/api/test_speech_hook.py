import base64
import socket

import httpx
import pytest

from app import config
from app.speech.hook import SpeechHook
from api_support import REPO_ROOT


def test_speech_hook_returns_none_without_a_network_call(monkeypatch):
    def create_connection(*args, **kwargs):
        raise AssertionError("socket.create_connection was called")

    monkeypatch.setattr(socket, "create_connection", create_connection)
    hook = SpeechHook()
    assert hook.transcribe(b"abc") is None
    assert hook.synthesize("hello") is None


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
    assert not (REPO_ROOT / "mobile").is_dir()


class _Response:
    def __init__(self, status_code, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload
        self.content = content

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _install_http(monkeypatch, response):
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "test-key")
    return calls


def test_elevenlabs_constants():
    assert config.ELEVENLABS_STT_MODEL == "scribe_v2_medical"
    assert config.ELEVENLABS_TTS_MODEL == "eleven_multilingual_v2"
    assert config.ELEVENLABS_VOICE_ID == "JBFqnCBsd6RMkjVDRZzb"
    assert config.ELEVENLABS_TTS_FORMAT == "mp3_44100_128"


def test_transcribe_posts_scribe_and_returns_stripped_text(monkeypatch):
    calls = _install_http(
        monkeypatch,
        _Response(200, {"text": "  Mark hypertension controlled.  "}),
    )

    assert SpeechHook().transcribe(b"abc") == "Mark hypertension controlled."

    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == "https://api.elevenlabs.io/v1/speech-to-text"
    assert kwargs["headers"]["xi-api-key"] == "test-key"
    assert kwargs["timeout"] == 60.0
    filename, payload = kwargs["files"]["file"][:2]
    assert filename == "audio"
    assert payload == b"abc"
    assert kwargs["data"]["model_id"] == "scribe_v2_medical"
    assert kwargs["data"]["language_code"] == "eng"
    assert "webhook" not in kwargs["data"]
    assert "diarize" not in kwargs["data"]
    assert "use_multi_channel" not in kwargs["data"]


def test_synthesize_posts_tts_and_returns_base64(monkeypatch):
    audio = b"mp3-bytes"
    calls = _install_http(monkeypatch, _Response(200, content=audio))

    assert SpeechHook().synthesize("Hello") == base64.b64encode(audio).decode("ascii")

    url, kwargs = calls[0]
    assert url == (
        "https://api.elevenlabs.io/v1/text-to-speech/"
        "JBFqnCBsd6RMkjVDRZzb?output_format=mp3_44100_128"
    )
    assert kwargs["headers"]["xi-api-key"] == "test-key"
    assert kwargs["json"] == {"text": "Hello", "model_id": "eleven_multilingual_v2"}
    assert kwargs["timeout"] == 30.0
    assert not url.startswith("data:")


@pytest.mark.parametrize(
    "method,response,audio",
    [
        ("transcribe", _Response(500, {"text": "nope"}), b"abc"),
        ("transcribe", _Response(200, {"text": "  "}), b"abc"),
        ("transcribe", _Response(200, {}), b"abc"),
        ("transcribe", httpx.TimeoutException("slow"), b"abc"),
        ("synthesize", _Response(500, content=b"nope"), "Hello"),
        ("synthesize", _Response(200, content=b""), "Hello"),
        ("synthesize", httpx.TimeoutException("slow"), "Hello"),
    ],
)
def test_speech_failures_return_none(monkeypatch, method, response, audio):
    _install_http(monkeypatch, response)
    assert getattr(SpeechHook(), method)(audio) is None


def test_set_key_only_calls_elevenlabs(monkeypatch):
    calls = _install_http(monkeypatch, _Response(200, {"text": "Hello"}))
    SpeechHook().transcribe(b"abc")
    host = calls[0][0].split("/")[2]
    assert host == "api.elevenlabs.io"
