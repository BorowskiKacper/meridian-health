import base64

import httpx
from sqlalchemy import func, select

from api_support import JANE_ID, assert_error, bind_session, call
from app.db.models import Request

TRANSCRIPT = "Mark hypertension controlled."
AUDIO = b"spoken-mp3"
REASON = "I will move the screening earlier."


class _Response:
    def __init__(self, status_code, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload
        self.content = content

    def json(self):
        return self._payload


def _request_count(session):
    return session.scalar(select(func.count()).select_from(Request))


def _baseline():
    return {
        "source_id": "uspstf:colorectal-cancer-screening#2",
        "title": "USPSTF Colorectal Cancer: Screening: Clinician Summary",
        "passage": "Screen adults aged 45 to 49 years for colorectal cancer.",
        "locator": (
            "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/"
            "colorectal-cancer-screening"
        ),
        "tier": "baseline",
    }


def _complete(route):
    def complete(task, payload):
        if task == "classify":
            return {"route": route}
        if task == "chart":
            return {"suggestions": []}
        if task == "research":
            return {
                "tool_calls": [],
                "answer": {"text": "LDL is above the cited range.", "citations": []},
                "recommends_action": False,
            }
        if task == "verify":
            return {
                "supported": [
                    {
                        "sentence": payload.get("text") or "",
                        "citation_indexes": list(range(len(payload.get("citations") or []))),
                    }
                ],
                "removed": [],
            }
        if task == "reminders":
            return {
                "tool_calls": [],
                "up_to_date": False,
                "answer": None,
                "suggestions": [
                    {
                        "request_id": None,
                        "kind": "reminder_change",
                        "status": "pending",
                        "target_table": "reminder_schedule",
                        "target_id": None,
                        "before": {"status": "scheduled"},
                        "after": {"due_on": "2026-12-01", "status": "scheduled"},
                        "reason": REASON,
                        "confidence": 0.8,
                        "citations": [_baseline()],
                        "validation_flags": [],
                        "source": "reminder_agent",
                    }
                ],
            }
        raise AssertionError(task)

    return complete


def _install(monkeypatch, *, scribe_status=200, route="chart_update"):
    calls = []

    def post(url, **kwargs):
        calls.append(url)
        if "speech-to-text" in url:
            return _Response(scribe_status, {"text": TRANSCRIPT})
        return _Response(200, content=AUDIO)

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr("app.config.ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr("app.agents.doctor.model.complete", _complete(route))
    return calls


def _post_audio(client):
    return call(
        client,
        "POST",
        "/requests",
        data={"patient_id": JANE_ID},
        files={"audio": ("request.webm", b"audio-bytes", "audio/webm")},
    )


def test_voice_routes_return_transcript_and_audio(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    expected_audio = base64.b64encode(AUDIO).decode("ascii")
    routes = ("chart_update", "clinical_question", "check_screenings")

    for route in routes:
        calls = _install(monkeypatch, route=route)
        response = _post_audio(client)
        assert response.status_code == 200
        body = response.json()
        assert body["transcript"] == TRANSCRIPT
        assert body["route"] == route, body
        assert isinstance(body["spoken_text"], str) and body["spoken_text"].strip(), body
        assert body["audio_base64"] == expected_audio
        assert any("speech-to-text" in url for url in calls)
        assert any("text-to-speech" in url for url in calls)


def test_typed_request_does_not_call_elevenlabs(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    calls = _install(monkeypatch)

    response = call(
        client,
        "POST",
        "/requests",
        data={"patient_id": JANE_ID, "text": "Mark hypertension controlled."},
    )

    assert response.status_code == 200
    assert calls == []


def test_failed_transcription_writes_no_request(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    before = _request_count(seeded_db.session)
    _install(monkeypatch, scribe_status=500)

    response = _post_audio(client)

    assert_error(response, 400, "validation_error")
    assert _request_count(seeded_db.session) == before
