from app.db.repositories import get_patient, list_conditions_by_patient, list_reminders_by_patient
from app.services.email import unsubscribe_token
from api_support import JANE_ID, JOHN_ID, bind_session, call

_SECRET = "unsubscribe-secret"


def _install_secret(monkeypatch):
    monkeypatch.setattr("app.config.EMAIL_UNSUBSCRIBE_SECRET", _SECRET)


def test_unsubscribe_opts_jane_out(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    _install_secret(monkeypatch)
    before_conditions = list_conditions_by_patient(seeded_db.session, JANE_ID)
    before_reminders = list_reminders_by_patient(seeded_db.session, JANE_ID)

    response = call(
        client,
        "GET",
        "/email/unsubscribe",
        params={"token": unsubscribe_token(JANE_ID)},
    )

    assert response.status_code == 200
    assert response.text == "You are unsubscribed from clinic reminders."
    jane = get_patient(seeded_db.session, JANE_ID)
    assert jane["email_opt_in"] is False
    assert jane["email"] == "jane.doe@example.com"
    assert list_conditions_by_patient(seeded_db.session, JANE_ID) == before_conditions
    assert list_reminders_by_patient(seeded_db.session, JANE_ID) == before_reminders


def test_bad_unsubscribe_token_changes_nothing(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    _install_secret(monkeypatch)

    response = call(
        client,
        "GET",
        "/email/unsubscribe",
        params={"token": "not-a-patient.deadbeef"},
    )

    assert response.status_code == 400
    assert response.text == "This unsubscribe link is not valid."
    assert get_patient(seeded_db.session, JANE_ID)["email_opt_in"] is True
    assert get_patient(seeded_db.session, JOHN_ID)["email_opt_in"] is False


def test_second_unsubscribe_stays_opted_out(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    _install_secret(monkeypatch)
    token = unsubscribe_token(JANE_ID)
    first = call(client, "GET", "/email/unsubscribe", params={"token": token})
    assert first.status_code == 200

    second = call(client, "GET", "/email/unsubscribe", params={"token": token})

    assert second.status_code == 200
    assert second.text == "You are unsubscribed from clinic reminders."
    assert get_patient(seeded_db.session, JANE_ID)["email_opt_in"] is False
