import socket

from app.speech.hook import SpeechHook
from support import REPO_ROOT


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
    assert not (REPO_ROOT / "web").is_dir()
    assert not (REPO_ROOT / "mobile").is_dir()
