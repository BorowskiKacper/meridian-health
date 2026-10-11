"""Exercise the real HTTP transaction lifecycle against the private test schema."""
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from api_support import AMY_ID, assert_error
from app import runtime
from app.db.models import AuditLog


def bind_request_database(monkeypatch, seeded_db):
    seeded_db.session.commit()
    connection = seeded_db.session.get_bind()
    monkeypatch.setattr(runtime, "get_engine", lambda: connection)
    # Keep each request inside the fixture's outer transaction for isolation.
    monkeypatch.setattr(runtime, "Session", lambda bind: Session(bind, join_transaction_mode="create_savepoint"))
    return connection


def test_request_write_survives_session_close_and_next_chart_read(client, seeded_db, monkeypatch):
    connection = bind_request_database(monkeypatch, seeded_db)
    submission_id = str(uuid4())
    response = client.post(f"/patients/{AMY_ID}/vitals", json={
        "submission_id": submission_id, "observed_at": "2025-10-10T14:15:00Z", "pulse": 87,
    })
    assert response.status_code == 200
    assert runtime.current_session() is None
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        assert session.get(AuditLog, UUID(submission_id)) is not None
    chart = client.get(f"/patients/{AMY_ID}/chart")
    assert chart.status_code == 200
    pulse = next(series for series in chart.json()["series"] if series["name"] == "Heart rate")
    assert any(point["value"] == 87 and point["source"] == "manual_entry" for point in pulse["points"])
    assert client.get("/patients/search", params={"q": "amy"}).json()["patients"][0]["id"] == AMY_ID


def test_error_response_rolls_back_request_write(client, seeded_db, monkeypatch):
    import app.services.chart_entries as entries

    connection = bind_request_database(monkeypatch, seeded_db)
    original = entries.record_vitals

    def reject_after_write(*args, **kwargs):
        assert original(*args, **kwargs)["saved"]
        return {"error": {"code": "invalid_state", "message": "Injected failure after capture."}}

    monkeypatch.setattr(entries, "record_vitals", reject_after_write)
    submission_id = str(uuid4())
    response = client.post(f"/patients/{AMY_ID}/vitals", json={
        "submission_id": submission_id, "observed_at": "2025-10-10T14:15:00Z", "pulse": 88,
    })
    assert_error(response, 409, "invalid_state")
    assert runtime.current_session() is None
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        assert session.get(AuditLog, UUID(submission_id)) is None


def test_approval_commits_a_note_without_launching_screenings(client, seeded_db, monkeypatch):
    bind_request_database(monkeypatch, seeded_db)
    monkeypatch.setattr("app.services.approval.embed_text", lambda body: [0.1] * 768)
    def unsolicited_review(*args, **kwargs):
        raise AssertionError("Approval must not launch screening review")
    monkeypatch.setattr("app.agents.doctor.run_reminder_agent", unsolicited_review)
    created = client.post("/suggestions", json={"patient_id": AMY_ID, "text": "Reviewed visit plan for approval regression test.", "citations": []})
    assert created.status_code == 200
    suggestion_id = created.json()["id"]
    approved = client.post("/suggestions/approve", json={"suggestion_ids": [suggestion_id]})
    assert approved.status_code == 200
    assert approved.json()["reminder_review"] == {"suggestions": [], "answer": None}
    chart = client.get(f"/patients/{AMY_ID}/chart")
    assert chart.status_code == 200
    assert any(note["source_suggestion_id"] == suggestion_id for note in chart.json()["notes"])
