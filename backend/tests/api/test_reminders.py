from app.db.repositories import list_reminders_by_patient
from support import AMY_ID, JANE_ID, UNKNOWN_ID, assert_error, bind_session, call

TWILIO_FROM = "whatsapp:+15550001111"


def _install_sms(monkeypatch):
    calls = []

    def send_whatsapp(from_number, to, body):
        calls.append((from_number, to, body))
        return "SM1"

    monkeypatch.setattr("app.services.sms.send_whatsapp", send_whatsapp)
    monkeypatch.setattr("app.config.TWILIO_FROM_NUMBER", TWILIO_FROM)
    return calls


def _reminder_named(session, patient_id, name):
    matches = [
        row
        for row in list_reminders_by_patient(session, patient_id)
        if row["name"] == name
    ]
    assert len(matches) == 1
    return matches[0]


def test_update_reminder_pauses_and_moves_the_due_date(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    reminder = _reminder_named(seeded_db.session, JANE_ID, "Colorectal cancer screening")

    response = call(
        client,
        "PUT",
        f"/patients/{JANE_ID}/reminders/{reminder['id']}",
        json={"due_on": "2026-12-01", "status": "paused"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) >= {"id", "patient_id", "name", "due_on", "status"}
    assert body["id"] == reminder["id"]
    assert body["patient_id"] == JANE_ID
    assert body["name"] == reminder["name"]
    assert body["due_on"] == "2026-12-01"
    assert body["status"] == "paused"


def test_update_unknown_reminder_is_not_found(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(
        client,
        "PUT",
        f"/patients/{JANE_ID}/reminders/{UNKNOWN_ID}",
        json={"due_on": "2026-12-01", "status": "paused"},
    )

    assert_error(response, 404, "not_found")


def test_update_reminder_rejects_unknown_status(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    reminder = _reminder_named(seeded_db.session, JANE_ID, "Colorectal cancer screening")

    response = call(
        client,
        "PUT",
        f"/patients/{JANE_ID}/reminders/{reminder['id']}",
        json={"status": "nope"},
    )

    assert_error(response, 400, "validation_error")


def test_run_reminders_sends_only_amy(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    _install_sms(monkeypatch)
    amy = _reminder_named(seeded_db.session, AMY_ID, "Follow-up labs")

    response = call(
        client,
        "POST",
        "/demo/run-reminders",
        json={"as_of": "2026-09-15"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"sent", "skipped"}
    assert len(body["sent"]) == 1
    sent = body["sent"][0]
    assert sent["reminder_id"] == amy["id"]
    assert isinstance(sent["sms_id"], str)
    assert sent["sms_id"]
