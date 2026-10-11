import pytest

from api_support import bind_session, call
from app.demo import cache


def fail_live(*args, **kwargs):
    pytest.fail("A scripted prompt called the live assistant")


@pytest.mark.parametrize("prompt", cache.PROMPTS, ids=lambda p: p["id"])
def test_scripted_requests_skip_every_model_call(prompt, seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    monkeypatch.setattr("app.agents.doctor.model.complete", fail_live)
    monkeypatch.setattr("app.integrations.gemini_json", fail_live)
    monkeypatch.setattr("app.agents.doctor._research_answer", fail_live)
    response = {"route": prompt["route"], "answer": {"text": "Captured answer", "citations": []}, "suggestions": [], "audio_base64": None, "spoken_text": None}
    monkeypatch.setattr(cache, "load_answers", lambda: {prompt["id"]: {"prompt": prompt, "response": response}})
    data = {"text": prompt["text"]}
    if prompt["patient_id"]:
        data.update(patient_id=prompt["patient_id"], route=prompt["route"])
        preview = call(client, "POST", "/requests/preview", data=data)
        assert preview.json()["route"] == prompt["route"]
    url = "/requests" if prompt["patient_id"] else "/chat"
    first = call(client, "POST", url, data=data)
    second = call(client, "POST", url, data=data)
    assert first.status_code == second.status_code == 200
    assert first.json()["answer"] == response["answer"]
    assert first.json()["request_id"] != second.json()["request_id"]


def test_exact_scope_and_missing_capture(monkeypatch):
    prompt = cache.PROMPTS[0]
    monkeypatch.setattr(cache, "load_answers", lambda: {})
    assert cache.cached_response(None, prompt["text"]) is None
    assert cache.cached_response(prompt["patient_id"], prompt["text"] + " ") is None
    assert cache.cached_response(prompt["patient_id"], prompt["text"])["error"]["code"] == "invalid_state"


def test_checked_in_captures_are_complete():
    answers = cache.load_answers()
    assert set(answers) == {p["id"] for p in cache.PROMPTS}
    for prompt in cache.PROMPTS:
        entry = answers[prompt["id"]]
        assert entry["prompt"] == prompt
        response = entry["response"]
        assert response["route"] == prompt["route"]
        assert response["suggestions"] or response["answer"]["text"]
        assert "request_id" not in response
        assert all("id" not in suggestion for suggestion in response["suggestions"])


def test_document_replay_creates_fresh_pending_proposals(seeded_db, monkeypatch, client):
    from app.db.repositories import get_suggestion, get_request
    prompt = next(p for p in cache.PROMPTS if p["route"] == "chart_update")
    bind_session(monkeypatch, seeded_db.session)
    monkeypatch.setattr("app.agents.doctor.model.complete", fail_live)
    data = {"patient_id": prompt["patient_id"], "text": prompt["text"], "route": prompt["route"]}
    first = call(client, "POST", "/requests", data=data).json()
    second = call(client, "POST", "/requests", data=data).json()
    assert first["suggestions"] and second["suggestions"]
    assert first["suggestions"][0]["id"] != second["suggestions"][0]["id"]
    for response in (first, second):
        assert get_request(seeded_db.session, response["request_id"])
        for proposal in response["suggestions"]:
            stored = get_suggestion(seeded_db.session, proposal["id"])
            assert stored["status"] == "pending"
            assert stored["request_id"] == response["request_id"]
