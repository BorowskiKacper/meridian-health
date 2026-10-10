from datetime import date

from app.db.repositories import list_conditions_by_patient, list_reminders_by_patient
from api_support import JANE_ID, bind_session, call, listed_ids

TEXT = "Mark hypertension controlled."
BASELINE = {
    "source_id": "uspstf:colorectal-cancer-screening#2",
    "title": "USPSTF Colorectal Cancer: Screening: Clinician Summary",
    "passage": (
        "For adults aged 45 to 49 years: Screen adults aged 45 to 49 years "
        "for colorectal cancer. Grade B"
    ),
    "locator": (
        "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/"
        "colorectal-cancer-screening"
    ),
    "tier": "baseline",
}


def _named(rows, name):
    matches = [row for row in rows if row.get("name") == name]
    assert len(matches) == 1
    return matches[0]


def _due_on(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return str(value)[:10]


def _install(monkeypatch):
    reminder_calls = {"count": 0}

    def complete(task, payload):
        if task == "classify":
            return {"route": "chart_update"}
        if task == "chart":
            condition = _named(payload["context"]["conditions"], "Hypertension")
            return {
                "suggestions": [
                    {
                        "patient_id": JANE_ID,
                        "request_id": None,
                        "kind": "field_update",
                        "status": "pending",
                        "target_table": "conditions",
                        "target_id": condition["id"],
                        "before": {"status": "active"},
                        "after": {"status": "controlled"},
                        "reason": "Mark it controlled.",
                        "confidence": 0.9,
                        "citations": [],
                        "validation_flags": [],
                        "source": "chart_agent",
                    }
                ]
            }
        if task == "reminders":
            reminder_calls["count"] += 1
            if reminder_calls["count"] == 1:
                screening = _named(
                    payload["context"]["reminders"],
                    "Colorectal cancer screening",
                )
                return {
                    "up_to_date": False,
                    "answer": None,
                    "tool_calls": [],
                    "suggestions": [
                        {
                            "patient_id": JANE_ID,
                            "request_id": None,
                            "kind": "reminder_change",
                            "status": "pending",
                            "target_table": "reminder_schedule",
                            "target_id": screening["id"],
                            "before": {
                                "due_on": _due_on(screening["due_on"]),
                                "status": "scheduled",
                            },
                            "after": {"due_on": "2026-12-01", "status": "scheduled"},
                            "reason": "USPSTF baseline: start at 45.",
                            "confidence": 0.9,
                            "citations": [dict(BASELINE)],
                            "validation_flags": [],
                            "source": "reminder_agent",
                        }
                    ],
                }
            return {
                "up_to_date": True,
                "answer": "Screenings are up to date.",
                "suggestions": [],
                "tool_calls": [],
            }
        if task == "verify":
            citations = payload.get("citations") or []
            return {
                "supported": [
                    {
                        "sentence": payload["text"],
                        "citation_indexes": list(range(len(citations))),
                    }
                ],
                "removed": [],
            }
        return {}

    def transcribe(self, audio):
        raise AssertionError("transcribe was called")

    def send_whatsapp(from_number, to, body):
        raise AssertionError("send_whatsapp was called")

    monkeypatch.setattr("app.agents.doctor.model.complete", complete)
    monkeypatch.setattr(
        "app.evidence.search_guidelines",
        lambda text, corpus: {"passages": []},
    )
    monkeypatch.setattr(
        "app.evidence.search_medical_web",
        lambda text: {"passages": []},
    )
    monkeypatch.setattr("app.services.sms.send_whatsapp", send_whatsapp)
    monkeypatch.setattr(
        "app.speech.hook.SpeechHook.transcribe",
        transcribe,
        raising=False,
    )


def _hypertension(session):
    return _named(list_conditions_by_patient(session, JANE_ID), "Hypertension")


def _screening(session):
    return _named(list_reminders_by_patient(session, JANE_ID), "Colorectal cancer screening")


def test_typed_update_approval_then_reminder_approval(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    _install(monkeypatch)
    session = seeded_db.session

    created = call(
        client,
        "POST",
        "/requests",
        data={"patient_id": JANE_ID, "text": TEXT},
    )

    assert created.status_code == 200
    created_body = created.json()
    assert created_body["route"] == "chart_update"
    assert created_body["answer"] is None
    assert len(created_body["suggestions"]) == 1
    suggestion_id = created_body["suggestions"][0]["id"]
    assert suggestion_id

    approved = call(
        client,
        "POST",
        "/suggestions/approve",
        json={"suggestion_ids": [suggestion_id]},
    )

    assert approved.status_code == 200
    approved_body = approved.json()
    assert suggestion_id in listed_ids(approved_body["approved"])
    review = approved_body["reminder_review"]
    assert len(review["suggestions"]) == 1
    reminder_suggestion = review["suggestions"][0]
    assert reminder_suggestion["kind"] == "reminder_change"
    assert reminder_suggestion["status"] == "pending"
    assert _hypertension(session)["status"] == "controlled"

    closed = call(
        client,
        "POST",
        "/suggestions/approve",
        json={"suggestion_ids": [reminder_suggestion["id"]]},
    )

    assert closed.status_code == 200
    closed_review = closed.json()["reminder_review"]
    assert closed_review["suggestions"] == []
    assert "up to date" in closed_review["answer"].lower()
    assert _screening(session)["due_on"] == date(2026, 12, 1)
