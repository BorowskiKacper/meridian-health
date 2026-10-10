from datetime import datetime, timezone
from uuid import uuid4

from app.db.repositories import (
    get_appointment,
    insert_appointment,
    list_appointments_by_patient,
    list_patients,
)
from app.db.repositories import update_appointment as update_appointment_row

_ALLOWED_STATUS = {"scheduled", "cancelled", "completed"}


def _error(code, message):
    return {"error": {"code": code, "message": message}}


def _zulu(value):
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return value


def _on_date(starts_at, on):
    if starts_at.tzinfo is None or starts_at.utcoffset() is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    return starts_at.astimezone(timezone.utc).date() == on


def _appointment(row):
    return {
        "id": row["id"],
        "patient_id": row["patient_id"],
        "starts_at": _zulu(row["starts_at"]),
        "ends_at": _zulu(row["ends_at"]),
        "reason": row["reason"],
        "status": row["status"],
    }


def list_appointments(patient_id, on, *, session):
    if patient_id is None:
        patient_ids = [row["id"] for row in list_patients(session)]
    else:
        patient_ids = [patient_id]
    rows = []
    for pid in patient_ids:
        rows.extend(list_appointments_by_patient(session, pid))
    if on is not None:
        rows = [row for row in rows if _on_date(row["starts_at"], on)]
    return {"appointments": [_appointment(row) for row in rows]}


def create_appointment(patient_id, starts_at, ends_at, reason, *, session):
    stored = insert_appointment(
        session,
        {
            "id": str(uuid4()),
            "patient_id": patient_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "reason": reason,
            "status": "scheduled",
        },
    )
    return _appointment(stored)


def update_appointment(
    appointment_id,
    starts_at=None,
    ends_at=None,
    reason=None,
    status=None,
    *,
    session,
):
    if status is not None and status not in _ALLOWED_STATUS:
        return _error(
            "validation_error",
            "Appointment status must be scheduled, cancelled, or completed.",
        )
    existing = get_appointment(session, appointment_id)
    if existing is None:
        return _error("not_found", "Appointment was not found.")
    fields = {}
    if starts_at is not None:
        fields["starts_at"] = starts_at
    if ends_at is not None:
        fields["ends_at"] = ends_at
    if reason is not None:
        fields["reason"] = reason
    if status is not None:
        fields["status"] = status
    if not fields:
        return _appointment(existing)
    updated = update_appointment_row(session, appointment_id, fields)
    if updated is None:
        return _error("not_found", "Appointment was not found.")
    return _appointment(updated)
