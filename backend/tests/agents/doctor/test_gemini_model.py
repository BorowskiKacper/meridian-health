import json

import pytest

from app import config
from app.agents.doctor.model import complete


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
        self.api_key = api_key
        self.models = _Client.models
        _Client.built.append(api_key)


def _install(monkeypatch, text):
    _Client.built = []
    _Client.models = _Models(text)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "gemini-key")
    monkeypatch.setattr("google.genai.Client", _Client)
    return _Client.models


def _schema_blob(call):
    schema = call["config"].response_schema
    return json.dumps(schema)


def test_classify_returns_each_route(monkeypatch):
    for route in ("chart_update", "clinical_question", "check_screenings"):
        models = _install(monkeypatch, json.dumps({"route": route}))
        assert complete("classify", {"text": "hello"}) == {"route": route}
        assert len(models.calls) == 1
        assert models.calls[0]["model"] == "gemini-3.6-flash"
        assert models.calls[0]["config"].response_mime_type == "application/json"


def test_other_tasks_return_their_json(monkeypatch):
    bodies = {
        "chart": {"suggestions": []},
        "research": {
            "answer": {"text": "", "citations": []},
            "recommends_action": False,
            "tool_calls": [],
        },
        "reminders": {
            "suggestions": [],
            "answer": "Screenings are up to date.",
            "up_to_date": True,
            "tool_calls": [],
        },
        "verify": {
            "supported": [
                {
                    "sentence": "Screen adults aged 45 to 49 years.",
                    "citation_indexes": [0],
                }
            ],
            "removed": [],
        },
    }
    for task, body in bodies.items():
        models = _install(monkeypatch, json.dumps(body))
        assert complete(task, {"text": "hello"}) == body
        assert len(models.calls) == 1


def test_research_schema_omits_forbidden_tools(monkeypatch):
    models = _install(monkeypatch, json.dumps({
        "answer": {"text": "", "citations": []},
        "recommends_action": False,
        "tool_calls": [],
    }))
    complete("research", {"text": "hello"})
    blob = _schema_blob(models.calls[0])
    assert "web_search" not in blob
    assert "propose_change" not in blob
    assert "search_guidelines" in blob
    assert "search_medical_web" in blob
    assert "search_patient_notes" in blob


def test_reminders_schema_omits_forbidden_tools(monkeypatch):
    models = _install(
        monkeypatch,
        json.dumps({
            "suggestions": [],
            "answer": "Screenings are up to date.",
            "up_to_date": True,
            "tool_calls": [],
        }),
    )
    complete("reminders", {"text": "hello"})
    blob = _schema_blob(models.calls[0])
    assert "web_search" not in blob
    assert "propose_change" not in blob
    assert "search_patient_notes" not in blob
    assert "search_guidelines" in blob
    assert "search_medical_web" in blob


def test_empty_key_raises_before_the_client_is_built(monkeypatch):
    _Client.built = []
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr("google.genai.Client", _Client)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not set"):
        complete("classify", {"text": "hello"})
    assert _Client.built == []


def test_unknown_task_and_invalid_json_raise(monkeypatch):
    _install(monkeypatch, "not-json")
    with pytest.raises(ValueError):
        complete("not-a-task", {})
    with pytest.raises(json.JSONDecodeError):
        complete("classify", {"text": "hello"})
