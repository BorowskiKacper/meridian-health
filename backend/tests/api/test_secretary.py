from api_support import (
    DOCTOR,
    JANE_ID,
    SECRETARY,
    assert_error,
    bind_session,
    call,
    install_secretary_model,
)

QUESTION = "Does this plan require prior auth?"
ANSWER = "This plan lists prior auth for the order."


def _install(monkeypatch):
    calls = []

    def complete(task, payload):
        calls.append((task, payload))
        return {
            "tool_calls": [
                {"name": "get_coverage"},
                {"name": "search_payer_docs", "text": "prior auth rules"},
                {"name": "web_search", "text": "appeal steps"},
            ],
            "answer": {"text": ANSWER, "citations": []},
        }

    def search_payer_docs(text):
        return {"passages": []}

    def web_search(text):
        return {"text": "", "citations": []}

    install_secretary_model(monkeypatch, complete)
    monkeypatch.setattr("app.evidence.search_payer_docs", search_payer_docs)
    monkeypatch.setattr("app.evidence.web_search", web_search)
    return calls


def test_secretary_request_returns_an_answer(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    _install(monkeypatch)

    response = call(
        client,
        "POST",
        "/secretary/requests",
        json={"patient_id": JANE_ID, "text": QUESTION},
        headers=SECRETARY,
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"request_id", "answer"}
    assert "suggestions" not in body
    assert body["answer"]["text"] == ANSWER
    assert body["request_id"]


def test_doctor_cannot_call_the_secretary(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    calls = _install(monkeypatch)

    response = call(
        client,
        "POST",
        "/secretary/requests",
        json={"patient_id": JANE_ID, "text": QUESTION},
        headers=DOCTOR,
    )

    assert_error(response, 403, "wrong_role")
    assert calls == []
