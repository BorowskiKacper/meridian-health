from app.db.repositories import list_reminders_by_patient
from api_support import AMY_ID, JANE_ID, UNKNOWN_ID, assert_error, bind_session, call


def _install_email(monkeypatch):
    calls = []

    def send_email(to_email, variables):
        calls.append((to_email, variables))
        return "re_1"

    monkeypatch.setattr("app.services.email.send_email", send_email)
    monkeypatch.setattr("app.config.EMAIL_PUBLIC_BASE_URL", "https://clinic.example")
    monkeypatch.setattr("app.config.EMAIL_UNSUBSCRIBE_SECRET", "unsubscribe-secret")
    return calls


def _reminder_named(session, patient_id, name):
    matches = [
        row
        for row in list_reminders_by_patient(session, patient_id)
        if row["name"] == name
    ]
    assert len(matches) == 1
    return matches[0]


def test_list_reminders_returns_jane_schedule(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(client, "GET", f"/patients/{JANE_ID}/reminders")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"reminders"}
    match = next(
        item for item in body["reminders"] if item["name"] == "Colorectal cancer screening"
    )
    assert match["patient_id"] == JANE_ID
    assert match["due_on"] == "2026-10-01"
    assert match["status"] == "scheduled"


def test_list_reminders_unknown_patient_is_not_found(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(client, "GET", f"/patients/{UNKNOWN_ID}/reminders")

    assert_error(response, 404, "not_found")


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
    _install_email(monkeypatch)
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
    assert isinstance(sent["email_id"], str)
    assert sent["email_id"]
