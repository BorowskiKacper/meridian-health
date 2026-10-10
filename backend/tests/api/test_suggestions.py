from uuid import uuid4

from app.db.repositories import (
    insert_suggestion,
    list_conditions_by_patient,
    list_notes_by_patient,
)
from support import JANE_ID, assert_error, bind_session, call, listed_ids

PLAN_TEXT = "Recheck lipids in 6 weeks"
REJECT_REASON = "Not accurate"
REMINDER_ANSWER = "Screenings are up to date."


def _install_model(monkeypatch):
    def complete(task, payload):
        if task == "reminders":
            return {
                "up_to_date": True,
                "answer": REMINDER_ANSWER,
                "suggestions": [],
                "tool_calls": [],
            }
        if task == "verify":
            citations = payload.get("citations") or []
            return {
                "supported": [
                    {
                        "sentence": payload.get("text", ""),
                        "citation_indexes": list(range(len(citations))),
                    }
                ],
                "removed": [],
            }
        return {}

    monkeypatch.setattr("app.agents.doctor.model.complete", complete)


def _suggestion(session, **overrides):
    row = {
        "id": str(uuid4()),
        "patient_id": JANE_ID,
        "request_id": None,
        "kind": "field_update",
        "status": "pending",
        "target_table": "conditions",
        "target_id": None,
        "before": {"status": "active"},
        "after": {"status": "controlled"},
        "reason": "Mark hypertension controlled.",
        "confidence": 0.9,
        "citations": [],
        "validation_flags": [],
        "source": "chart_agent",
    }
    row.update(overrides)
    return insert_suggestion(session, row)


def _hypertension(session):
    matches = [
        row
        for row in list_conditions_by_patient(session, JANE_ID)
        if row["name"] == "Hypertension"
    ]
    assert len(matches) == 1
    return matches[0]


def test_list_pending_suggestions(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    session = seeded_db.session
    pending = _suggestion(session)
    approved = _suggestion(session, status="approved")

    response = call(
        client,
        "GET",
        "/suggestions",
        params={"patient_id": JANE_ID, "status": "pending"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"suggestions"}
    assert pending["id"] in listed_ids(body["suggestions"])
    assert approved["id"] not in listed_ids(body["suggestions"])
    assert all(item["status"] == "pending" for item in body["suggestions"])


def test_list_suggestions_defaults_to_pending(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    session = seeded_db.session
    pending = _suggestion(session)
    approved = _suggestion(session, status="approved")

    response = call(
        client,
        "GET",
        "/suggestions",
        params={"patient_id": JANE_ID},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"suggestions"}
    assert pending["id"] in listed_ids(body["suggestions"])
    assert approved["id"] not in listed_ids(body["suggestions"])
    assert all(item["status"] == "pending" for item in body["suggestions"])


def test_create_plan_item_does_not_write_a_note(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    session = seeded_db.session
    notes_before = [note["id"] for note in list_notes_by_patient(session, JANE_ID)]

    response = call(
        client,
        "POST",
        "/suggestions",
        json={
            "patient_id": JANE_ID,
            "request_id": None,
            "text": PLAN_TEXT,
            "citations": [],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "research_add_to_plan"
    assert body["kind"] == "plan_item"
    assert body["status"] == "pending"
    assert [note["id"] for note in list_notes_by_patient(session, JANE_ID)] == notes_before


def test_approve_field_update_marks_hypertension_controlled(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    _install_model(monkeypatch)
    session = seeded_db.session
    condition = _hypertension(session)
    suggestion = _suggestion(session, target_id=condition["id"])

    response = call(
        client,
        "POST",
        "/suggestions/approve",
        json={"suggestion_ids": [suggestion["id"]]},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"approved", "reminder_review"}
    assert suggestion["id"] in listed_ids(body["approved"])
    review = body["reminder_review"]
    assert set(review) >= {"suggestions", "answer"}
    updated = _hypertension(session)
    assert updated["status"] == "controlled"


def test_approve_already_approved_suggestion_is_invalid_state(
    seeded_db, monkeypatch, client
):
    bind_session(monkeypatch, seeded_db.session)
    _install_model(monkeypatch)
    suggestion = _suggestion(seeded_db.session, status="approved")

    response = call(
        client,
        "POST",
        "/suggestions/approve",
        json={"suggestion_ids": [suggestion["id"]]},
    )

    assert_error(response, 409, "invalid_state")


def test_reject_pending_field_update_leaves_the_chart(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    session = seeded_db.session
    condition = _hypertension(session)
    suggestion = _suggestion(session, target_id=condition["id"])

    response = call(
        client,
        "POST",
        "/suggestions/reject",
        json={"suggestion_ids": [suggestion["id"]], "reason": REJECT_REASON},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"rejected"}
    assert suggestion["id"] in listed_ids(body["rejected"])
    assert _hypertension(session)["status"] == "active"


def test_approve_edit_outside_the_allowlist_is_validation_error(
    seeded_db, monkeypatch, client
):
    bind_session(monkeypatch, seeded_db.session)
    _install_model(monkeypatch)
    session = seeded_db.session
    condition = _hypertension(session)
    suggestion = _suggestion(session, target_id=condition["id"])

    response = call(
        client,
        "POST",
        "/suggestions/approve",
        json={
            "suggestion_ids": [suggestion["id"]],
            "edits": {suggestion["id"]: {"after": {"secret": "x"}}},
        },
    )

    assert_error(response, 400, "validation_error")
    assert _hypertension(session)["status"] == "active"
