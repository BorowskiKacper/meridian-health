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
# Demo inbox. An explicit "send the reminder now" delivers only that patient's
# scheduled reminders here, so every chart can be practiced from one mailbox.
DEMO_REMINDER_TO = "vicchen199@gmail.com"


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


def _due_scheduled(patient_id, as_of, session, *, include_future=False):
    for reminder in list_reminders_by_patient(session, patient_id):
        if reminder["status"] != "scheduled":
            continue
        if not include_future and _as_date(reminder["due_on"]) > as_of:
            continue
        yield reminder


def _deliver_reminder(patient, reminder, *, session, to_email=None, ignore_opt_out=False):
    import app.services.email as email

    reminder_id = str(reminder["id"])
    if not ignore_opt_out and patient["email_opt_in"] is not True:
        return None, {"reminder_id": reminder_id, "reason": "opted_out"}
    address = to_email or patient["email"]
    link = email.unsubscribe_link(patient["id"])
    due_on = reminder["due_on"]
    body = email.reminder_text(patient["display_name"], reminder["name"], due_on, link)
    variables = email.template_variables(
        patient["display_name"], reminder["name"], due_on, link
    )
    provider_id = email.send_email(address, variables)
    email_id = str(uuid4())
    insert_email_message(
        session,
        {
            "id": email_id,
            "patient_id": str(patient["id"]),
            "reminder_id": reminder_id,
            "to_email": address,
            "body": body,
            "provider_id": provider_id,
            "status": "sent",
        },
    )
    save_reminder(session, reminder_id, {"status": "sent"})
    return {"reminder_id": reminder_id, "email_id": email_id}, None


def _collect_sends(patients, as_of, session, *, include_future=False, to_email=None, ignore_opt_out=False):
    sent = []
    skipped = []
    for patient in patients:
        for reminder in _due_scheduled(patient["id"], as_of, session, include_future=include_future):
            delivered, skip = _deliver_reminder(
                patient,
                reminder,
                session=session,
                to_email=to_email,
                ignore_opt_out=ignore_opt_out,
            )
            if skip is None:
                sent.append(delivered)
            else:
                skipped.append(skip)
    return {"sent": sent, "skipped": skipped}


def send_due_reminders(as_of, *, session):
    return _collect_sends(list_patients(session), as_of, session)


def send_patient_reminders(
    patient_id,
    as_of,
    *,
    session,
    to_email=None,
    include_future=False,
    ignore_opt_out=False,
):
    patient = get_patient(session, patient_id)
    if patient is None:
        return _error("not_found", "Patient was not found.")
    return _collect_sends(
        [patient],
        as_of,
        session,
        include_future=include_future,
        to_email=to_email,
        ignore_opt_out=ignore_opt_out,
    )


def reminder_send_message(result, *, patient_name=None, include_future=False):
    sent = result["sent"]
    skipped = result["skipped"]
    target = f" for {patient_name}" if patient_name else ""
    if sent:
        message = (
            f"Sent the reminder email{target}."
            if len(sent) == 1
            else f"Sent {len(sent)} reminder emails{target}."
        )
        if any(item["reason"] == "opted_out" for item in skipped):
            message += " A reminder was skipped because the patient is opted out of email."
        return message
    if any(item["reason"] == "opted_out" for item in skipped):
        return "No email was sent. This patient is opted out of reminders."
    if include_future:
        return "No email was sent. There is no scheduled reminder."
    return "No email was sent. There is no scheduled reminder that is due."


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
