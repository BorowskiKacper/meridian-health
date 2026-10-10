import pytest

from app.db.repositories import list_appointments_by_patient
from api_support import (
    DOCTOR,
    JANE_ID,
    JOHN_ID,
    SECRETARY,
    UNKNOWN_ID,
    assert_error,
    bind_session,
    call,
)

NEW_VISIT = {
    "patient_id": JANE_ID,
    "starts_at": "2026-11-02T15:00:00Z",
    "ends_at": "2026-11-02T15:30:00Z",
    "reason": "New visit",
}


def _jane_appointment(session):
    matches = [
        row
        for row in list_appointments_by_patient(session, JANE_ID)
        if row["reason"] == "Follow-up"
    ]
    assert len(matches) == 1
    return matches[0]


def test_list_appointments_for_jane(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(
        client,
        "GET",
        "/appointments",
        params={"patient_id": JANE_ID},
        headers=SECRETARY,
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"appointments"}
    assert any(item["reason"] == "Follow-up" for item in body["appointments"])


def test_list_appointments_on_johns_day(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(
        client,
        "GET",
        "/appointments",
        params={"on": "2026-10-11"},
        headers=SECRETARY,
    )

    assert response.status_code == 200
    appointments = response.json()["appointments"]
    assert any(item["patient_id"] == JOHN_ID for item in appointments)
    assert all(item["reason"] != "Follow-up" for item in appointments)


def test_create_appointment(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(
        client,
        "POST",
        "/appointments",
        json=NEW_VISIT,
        headers=SECRETARY,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "scheduled"
    assert body["starts_at"] == NEW_VISIT["starts_at"]
    assert body["ends_at"] == NEW_VISIT["ends_at"]
    assert body["reason"] == "New visit"
    assert body["patient_id"] == JANE_ID


def test_complete_appointment(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    appointment = _jane_appointment(seeded_db.session)

    response = call(
        client,
        "PUT",
        f"/appointments/{appointment['id']}",
        json={"status": "completed"},
        headers=SECRETARY,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_appointment_status_noshow_is_validation_error(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    appointment = _jane_appointment(seeded_db.session)

    response = call(
        client,
        "PUT",
        f"/appointments/{appointment['id']}",
        json={"status": "noshow"},
        headers=SECRETARY,
    )

    assert_error(response, 400, "validation_error")


def test_unknown_appointment_is_not_found(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(
        client,
        "PUT",
        f"/appointments/{UNKNOWN_ID}",
        json={"status": "completed"},
        headers=SECRETARY,
    )

    assert_error(response, 404, "not_found")


@pytest.mark.parametrize("headers", [DOCTOR, {}])
@pytest.mark.parametrize("action", ["get", "post", "put"])
def test_doctor_cannot_use_the_appointment_book(
    seeded_db, monkeypatch, client, headers, action
):
    bind_session(monkeypatch, seeded_db.session)
    appointment = _jane_appointment(seeded_db.session)
    if action == "get":
        response = call(
            client,
            "GET",
            "/appointments",
            params={"patient_id": JANE_ID},
            headers=headers,
        )
    elif action == "post":
        response = call(
            client,
            "POST",
            "/appointments",
            json=NEW_VISIT,
            headers=headers,
        )
    else:
        response = call(
            client,
            "PUT",
            f"/appointments/{appointment['id']}",
            json={"status": "completed"},
            headers=headers,
        )

    assert_error(response, 403, "wrong_role")
