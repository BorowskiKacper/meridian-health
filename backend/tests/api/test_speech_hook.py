import base64
import httpx
import pytest

from app.speech.hook import SpeechHook
from api_support import REPO_ROOT


def test_speech_hook_uses_provider_and_returns_transcript_and_audio(monkeypatch):
    from app import config
    from app.speech.hook import _voice
    _voice.cache_clear()
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr(config, "ELEVENLABS_VOICE_ID", "test-voice")
    calls = []
    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return httpx.Response(200, json={"text": "Test dictation."}, request=httpx.Request(method, url)) if url.endswith("speech-to-text") else httpx.Response(200, content=b"mp3", request=httpx.Request(method, url))
    monkeypatch.setattr(httpx, "request", request)
    hook = SpeechHook()
    assert hook.transcribe(b"abc") == "Test dictation."
    assert base64.b64decode(hook.synthesize("hello")) == b"mp3"
    assert calls[0][2]["files"]["file"][1] == b"abc"
    assert calls[1][2]["json"]["text"] == "hello"


def test_speech_provider_failure_is_safe(monkeypatch):
    from app import config
    from app.integrations import IntegrationError
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "secret-test-key")
    def fail(*args, **kwargs):
        raise RuntimeError("Provider rejected secret-test-key")
    monkeypatch.setattr(httpx, "request", fail)
    with pytest.raises(IntegrationError) as error:
        SpeechHook().transcribe(b"abc")
    assert "secret-test-key" not in str(error.value)


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
