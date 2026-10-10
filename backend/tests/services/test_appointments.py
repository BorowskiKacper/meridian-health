import re
from datetime import date, datetime, timezone

from app.db.repositories import get_appointment, list_appointments_by_patient
from app.services.appointments import (
    create_appointment,
    list_appointments,
    update_appointment,
)

JANE_ID = "11111111-1111-4111-8111-111111111111"
JOHN_ID = "22222222-2222-4222-8222-222222222222"
AMY_ID = "33333333-3333-4333-8333-333333333333"
PATIENT_IDS = (JANE_ID, JOHN_ID, AMY_ID)
UNKNOWN_APPOINTMENT_ID = "88888888-8888-4888-8888-888888888888"

JANE_START = datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc)
JANE_END = datetime(2026, 10, 10, 15, 30, tzinfo=timezone.utc)
JOHN_START = "2026-10-11T15:00:00Z"

ZULU = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
APPOINTMENT_KEYS = {
    "id",
    "patient_id",
    "starts_at",
    "ends_at",
    "reason",
    "status",
}
ALLOWED_STATUS = {"scheduled", "cancelled", "completed"}


def invoke(fn, *args, session, **kwargs):
    import inspect

    if "session" in inspect.signature(fn).parameters:
        kwargs["session"] = session
    return fn(*args, **kwargs)


def zulu(value):
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def assert_error(body, code):
    assert isinstance(body, dict)
    assert set(body) == {"error"}
    error = body["error"]
    assert isinstance(error, dict)
    assert set(error) == {"code", "message"}
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert error["message"].strip()


def project(row):
    return {
        "id": row["id"],
        "patient_id": row["patient_id"],
        "starts_at": zulu(row["starts_at"]),
        "ends_at": zulu(row["ends_at"]),
        "reason": row["reason"],
        "status": row["status"],
    }


def stored_appointments(session, patient_id, on):
    if patient_id is None:
        patient_ids = PATIENT_IDS
    else:
        patient_ids = (patient_id,)
    rows = []
    for pid in patient_ids:
        rows.extend(list_appointments_by_patient(session, pid))
    if on is not None:
        rows = [
            row
            for row in rows
            if row["starts_at"].astimezone(timezone.utc).date() == on
        ]
    return rows


def assert_appointment_list(body, rows):
    assert isinstance(body, dict)
    assert set(body) == {"appointments"}
    appointments = body["appointments"]
    assert isinstance(appointments, list)
    for item in appointments:
        assert set(item) == APPOINTMENT_KEYS
        assert isinstance(item["id"], str) and item["id"]
        assert isinstance(item["patient_id"], str) and item["patient_id"]
        assert isinstance(item["reason"], str) and item["reason"]
        assert item["status"] in ALLOWED_STATUS
        assert ZULU.fullmatch(item["starts_at"])
        assert ZULU.fullmatch(item["ends_at"])
    assert sorted(appointments, key=lambda item: item["id"]) == sorted(
        (project(row) for row in rows),
        key=lambda item: item["id"],
    )


def assert_on_date(appointments, on):
    for item in appointments:
        assert item["starts_at"][:10] == on.isoformat()


def jane_follow_up(session):
    matches = [
        row
        for row in list_appointments_by_patient(session, JANE_ID)
        if row["reason"] == "Follow-up"
        and row["starts_at"].astimezone(timezone.utc) == JANE_START
    ]
    assert len(matches) == 1
    return matches[0]


def test_list_appointments_for_jane(seeded_db):
    session = seeded_db.session
    body = invoke(list_appointments, JANE_ID, None, session=session)

    assert_appointment_list(body, stored_appointments(session, JANE_ID, None))
    follow_ups = [
        item for item in body["appointments"] if item["reason"] == "Follow-up"
    ]
    assert len(follow_ups) == 1
    appointment = follow_ups[0]
    assert appointment["patient_id"] == JANE_ID
    assert appointment["status"] == "scheduled"
    assert appointment["starts_at"] == "2026-10-10T15:00:00Z"
    assert appointment["ends_at"] == "2026-10-10T15:30:00Z"
    assert all(item["patient_id"] == JANE_ID for item in body["appointments"])
    john_ids = {row["id"] for row in list_appointments_by_patient(session, JOHN_ID)}
    listed_ids = {item["id"] for item in body["appointments"]}
    assert john_ids.isdisjoint(listed_ids)


def test_list_appointments_filters_jane_by_day(seeded_db):
    session = seeded_db.session
    tenth = date(2026, 10, 10)
    eleventh = date(2026, 10, 11)

    on_tenth = invoke(list_appointments, JANE_ID, tenth, session=session)
    assert_appointment_list(on_tenth, stored_appointments(session, JANE_ID, tenth))
    assert_on_date(on_tenth["appointments"], tenth)
    assert any(
        item["reason"] == "Follow-up" and item["starts_at"] == "2026-10-10T15:00:00Z"
        for item in on_tenth["appointments"]
    )

    on_eleventh = invoke(list_appointments, JANE_ID, eleventh, session=session)
    assert_appointment_list(
        on_eleventh,
        stored_appointments(session, JANE_ID, eleventh),
    )
    assert_on_date(on_eleventh["appointments"], eleventh)
    assert all(
        item["starts_at"] != "2026-10-10T15:00:00Z"
        for item in on_eleventh["appointments"]
    )
    assert all(item["reason"] != "Follow-up" for item in on_eleventh["appointments"])


def test_list_appointments_on_day_without_patient(seeded_db):
    session = seeded_db.session
    on_day = date(2026, 10, 11)
    body = invoke(list_appointments, None, on_day, session=session)

    assert_appointment_list(body, stored_appointments(session, None, on_day))
    assert_on_date(body["appointments"], on_day)
    assert any(
        item["patient_id"] == JOHN_ID
        and item["reason"] == "Pulmonary follow-up"
        and item["starts_at"] == JOHN_START
        for item in body["appointments"]
    )
    assert all(item["patient_id"] != JANE_ID for item in body["appointments"])
    assert all(item["reason"] != "Follow-up" for item in body["appointments"])
    assert all(
        item["starts_at"] != "2026-10-10T15:00:00Z" for item in body["appointments"]
    )


def test_create_appointment_stores_scheduled(seeded_db):
    session = seeded_db.session
    starts_at = datetime(2026, 11, 3, 14, 15, tzinfo=timezone.utc)
    ends_at = datetime(2026, 11, 3, 14, 45, tzinfo=timezone.utc)
    created = invoke(
        create_appointment,
        JANE_ID,
        starts_at,
        ends_at,
        "Blood pressure check",
        session=session,
    )

    assert set(created) == APPOINTMENT_KEYS
    assert isinstance(created["id"], str) and created["id"]
    assert created["patient_id"] == JANE_ID
    assert created["starts_at"] == "2026-11-03T14:15:00Z"
    assert created["ends_at"] == "2026-11-03T14:45:00Z"
    assert created["reason"] == "Blood pressure check"
    assert created["status"] == "scheduled"

    stored = get_appointment(session, created["id"])
    assert stored["patient_id"] == JANE_ID
    assert stored["reason"] == "Blood pressure check"
    assert stored["status"] == "scheduled"
    assert stored["starts_at"].astimezone(timezone.utc) == starts_at
    assert stored["ends_at"].astimezone(timezone.utc) == ends_at

    listed = invoke(list_appointments, JANE_ID, None, session=session)
    assert any(
        item["id"] == created["id"]
        and item["patient_id"] == JANE_ID
        and item["status"] == "scheduled"
        and item["reason"] == "Blood pressure check"
        and item["starts_at"] == "2026-11-03T14:15:00Z"
        and item["ends_at"] == "2026-11-03T14:45:00Z"
        for item in listed["appointments"]
    )


def test_update_appointment_changes_given_fields_and_rejects_noshow(seeded_db):
    session = seeded_db.session
    original = jane_follow_up(session)
    new_starts = datetime(2026, 10, 10, 16, 0, tzinfo=timezone.utc)
    updated = invoke(
        update_appointment,
        original["id"],
        session=session,
        starts_at=new_starts,
        ends_at=None,
        reason="Done",
        status="completed",
    )

    assert set(updated) == APPOINTMENT_KEYS
    assert updated["id"] == original["id"]
    assert updated["patient_id"] == JANE_ID
    assert updated["starts_at"] == "2026-10-10T16:00:00Z"
    assert updated["ends_at"] == "2026-10-10T15:30:00Z"
    assert updated["reason"] == "Done"
    assert updated["status"] == "completed"

    stored = get_appointment(session, original["id"])
    assert stored["status"] == "completed"
    assert stored["reason"] == "Done"
    assert stored["starts_at"].astimezone(timezone.utc) == new_starts
    assert stored["ends_at"].astimezone(timezone.utc) == JANE_END

    rejected = invoke(
        update_appointment,
        original["id"],
        session=session,
        status="noshow",
    )
    assert_error(rejected, "validation_error")

    after = get_appointment(session, original["id"])
    assert after["status"] == "completed"
    assert after["reason"] == "Done"
    assert after["starts_at"].astimezone(timezone.utc) == new_starts
    assert after["ends_at"].astimezone(timezone.utc) == JANE_END


def test_update_unknown_appointment(seeded_db):
    session = seeded_db.session
    assert get_appointment(session, UNKNOWN_APPOINTMENT_ID) is None

    body = invoke(
        update_appointment,
        UNKNOWN_APPOINTMENT_ID,
        session=session,
        status="cancelled",
    )

    assert_error(body, "not_found")
    assert get_appointment(session, UNKNOWN_APPOINTMENT_ID) is None
