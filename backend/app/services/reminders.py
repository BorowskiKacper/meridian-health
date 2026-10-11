from datetime import date, datetime
from uuid import uuid4

from app.db.repositories import (
    get_patient,
    get_reminder,
    insert_email_message,
    list_patients,
    list_reminders_by_patient,
    update_reminder as save_reminder,
)

_REMINDER_STATUSES = frozenset({"scheduled", "paused", "sent", "done"})
_CLINIC_REMINDER = (
    "You have a clinic reminder. Please contact the office to schedule a visit."
)


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    return value


def _iso_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _error(code, message):
    return {"error": {"code": code, "message": message}}


def send_due_reminders(as_of, *, session):
    import app.services.email as email

    sent = []
    skipped = []
    for patient in list_patients(session):
        for reminder in list_reminders_by_patient(session, patient["id"]):
            if reminder["status"] != "scheduled":
                continue
            if _as_date(reminder["due_on"]) > as_of:
                continue
            reminder_id = str(reminder["id"])
            if patient["email_opt_in"] is not True:
                skipped.append({"reminder_id": reminder_id, "reason": "opted_out"})
                continue
            to_email = patient["email"]
            body = _CLINIC_REMINDER + "\n" + email.unsubscribe_link(patient["id"])
            provider_id = email.send_email(to_email, body)
            email_id = str(uuid4())
            insert_email_message(
                session,
                {
                    "id": email_id,
                    "patient_id": str(patient["id"]),
                    "reminder_id": reminder_id,
                    "to_email": to_email,
                    "body": body,
                    "provider_id": provider_id,
                    "status": "sent",
                },
            )
            save_reminder(session, reminder_id, {"status": "sent"})
            sent.append({"reminder_id": reminder_id, "email_id": email_id})
    return {"sent": sent, "skipped": skipped}


def list_patient_reminders(patient_id, *, session):
    patient = get_patient(session, patient_id)
    if patient is None:
        return _error("not_found", "Patient was not found.")
    reminders = [
        {
            "id": str(row["id"]),
            "patient_id": str(row["patient_id"]),
            "name": row["name"],
            "due_on": _iso_date(row["due_on"]),
            "status": row["status"],
        }
        for row in list_reminders_by_patient(session, patient_id)
    ]
    reminders.sort(key=lambda item: (item["due_on"], item["name"]))
    return {"reminders": reminders}


def update_reminder(patient_id, reminder_id, due_on, status, *, session):
    row = get_reminder(session, reminder_id)
    if row is None or str(row["patient_id"]) != str(patient_id):
        return _error("not_found", "Reminder not found.")
    if status is not None and status not in _REMINDER_STATUSES:
        return _error(
            "validation_error",
            "Status must be scheduled, paused, sent, or done.",
        )
    fields = {}
    if due_on is not None:
        fields["due_on"] = due_on
    if status is not None:
        fields["status"] = status
    if fields:
        row = save_reminder(session, reminder_id, fields)
    return {
        "id": str(row["id"]),
        "patient_id": str(row["patient_id"]),
        "name": row["name"],
        "due_on": _iso_date(row["due_on"]),
        "status": row["status"],
    }
