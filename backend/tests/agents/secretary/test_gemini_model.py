import json

import pytest

from app import config
from app.agents.secretary.model import complete


class _Models:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {"text": self.text})()


class _Client:
    built = []

    def __init__(self, api_key):
        self.models = _Client.models
        _Client.built.append(api_key)


def test_secretary_complete_returns_json(monkeypatch):
    body = {"tool_calls": [], "answer": {"text": "", "citations": []}}
    _Client.built = []
    _Client.models = _Models(json.dumps(body))
    monkeypatch.setattr(config, "GEMINI_API_KEY", "gemini-key")
    monkeypatch.setattr("google.genai.Client", _Client)

    assert complete("secretary", {"text": "Does this need prior auth?"}) == body
    call = _Client.models.calls[0]
    assert call["model"] == "gemini-3.6-flash"
    assert call["config"].response_mime_type == "application/json"
    blob = json.dumps(call["config"].response_schema)
    assert "get_coverage" in blob
    assert "search_payer_docs" in blob
    assert "web_search" in blob
    assert "propose_change" not in blob


def test_empty_key_and_unknown_task(monkeypatch):
    _Client.built = []
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr("google.genai.Client", _Client)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not set"):
        complete("secretary", {"text": "hello"})
    assert _Client.built == []

    monkeypatch.setattr(config, "GEMINI_API_KEY", "gemini-key")
    with pytest.raises(ValueError):
        complete("classify", {"text": "hello"})
