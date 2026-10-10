"""Read and write Tiger rows. Callers pass the session they already own."""

import json
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Appointment,
    AuditLog,
    BodyRegion,
    Condition,
    Coverage,
    Document,
    EligibilityCheck,
    Encounter,
    FamilyHistory,
    Medication,
    Note,
    Observation,
    Patient,
    Reminder,
    ReminderRule,
    Request,
    SmsMessage,
    SpecialtyFocus,
    Suggestion,
)

_UUID_COLUMNS = frozenset(
    {
        "id",
        "patient_id",
        "document_id",
        "source_suggestion_id",
        "request_id",
        "target_id",
        "suggestion_id",
        "reminder_id",
        "rule_id",
        "coverage_id",
    }
)
_DATE_COLUMNS = frozenset({"date_of_birth", "onset_date", "start_date", "due_on"})
_LIST_COLUMNS = frozenset({"benefits", "citations", "validation_flags"})
_DICT_COLUMNS = frozenset({"before", "after"})


def _uuid(value):
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _bind_value(key, value):
    if value is None or key not in _UUID_COLUMNS:
        return value
    return _uuid(value)


def _json_collection(value, factory):
    if isinstance(value, str):
        value = json.loads(value)
    return factory(value)


def _embedding(value):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if text == "[]":
            return []
        if text.startswith("[") and text.endswith("]"):
            return [float(part) for part in text[1:-1].split(",") if part.strip()]
    return [float(item) for item in value]


def _present(key, value):
    if isinstance(value, uuid.UUID):
        return str(value)
    if key == "embedding":
        return _embedding(value)
    if key in _LIST_COLUMNS and value is not None:
        return _json_collection(value, list)
    if key in _DICT_COLUMNS and value is not None:
        return _json_collection(value, dict)
    if isinstance(value, datetime) and key in _DATE_COLUMNS:
        return value.date()
    if isinstance(value, datetime) and (value.tzinfo is None or value.utcoffset() is None):
        return value.replace(tzinfo=timezone.utc)
    return value


def _dump(instance):
    return {
        column.key: _present(column.key, getattr(instance, column.key))
        for column in instance.__table__.columns
    }


def _persist(session, instance):
    session.add(instance)
    session.flush()
    session.refresh(instance)
    return _dump(instance)


def _insert(session, model, row):
    instance = model(**{key: _bind_value(key, value) for key, value in row.items()})
    return _persist(session, instance)


def _update(session, model, row_id, fields):
    instance = session.get(model, _uuid(row_id))
    if instance is None:
        return None
    for key, value in fields.items():
        setattr(instance, key, _bind_value(key, value))
    session.flush()
    session.refresh(instance)
    return _dump(instance)


def _get(session, model, row_id):
    instance = session.get(model, _uuid(row_id))
    if instance is None:
        return None
    return _dump(instance)


def _list_where(session, model, *criteria):
    statement = select(model)
    if criteria:
        statement = statement.where(*criteria)
    return [_dump(row) for row in session.scalars(statement).all()]


def _by_patient(session, model, patient_id):
    return _list_where(session, model, model.patient_id == _uuid(patient_id))


def _by_patient_region(session, model, patient_id, body_region_key):
    return _list_where(
        session,
        model,
        model.patient_id == _uuid(patient_id),
        model.body_region_key == body_region_key,
    )


def _first_where(session, model, criterion):
    instance = session.scalars(select(model).where(criterion)).first()
    if instance is None:
        return None
    return _dump(instance)


def insert_patient(session: Session, row):
    return _insert(session, Patient, row)


def update_patient(session: Session, row_id, fields):
    return _update(session, Patient, row_id, fields)


def get_patient(session: Session, patient_id):
    return _get(session, Patient, patient_id)


def list_patients(session: Session):
    return _list_where(session, Patient)


def insert_condition(session: Session, row):
    return _insert(session, Condition, row)


def update_condition(session: Session, row_id, fields):
    return _update(session, Condition, row_id, fields)


def list_conditions_by_patient(session: Session, patient_id):
    return _by_patient(session, Condition, patient_id)


def list_conditions_by_region(session: Session, patient_id, body_region_key):
    return _by_patient_region(session, Condition, patient_id, body_region_key)


def insert_medication(session: Session, row):
    return _insert(session, Medication, row)


def update_medication(session: Session, row_id, fields):
    return _update(session, Medication, row_id, fields)


def list_medications_by_patient(session: Session, patient_id):
    return _by_patient(session, Medication, patient_id)


def list_medications_by_region(session: Session, patient_id, body_region_key):
    return _by_patient_region(session, Medication, patient_id, body_region_key)


def insert_family_history(session: Session, row):
    return _insert(session, FamilyHistory, row)


def update_family_history(session: Session, row_id, fields):
    return _update(session, FamilyHistory, row_id, fields)


def list_family_history_by_patient(session: Session, patient_id):
    return _by_patient(session, FamilyHistory, patient_id)


def insert_observation(session: Session, row):
    return _insert(session, Observation, row)


def update_observation(session: Session, row_id, fields):
    return _update(session, Observation, row_id, fields)


def list_observations_by_patient(session: Session, patient_id):
    return _by_patient(session, Observation, patient_id)


def list_observations_by_region(session: Session, patient_id, body_region_key):
    return _by_patient_region(session, Observation, patient_id, body_region_key)


def insert_encounter(session: Session, row):
    return _insert(session, Encounter, row)


def list_encounters_by_patient(session: Session, patient_id):
    return _by_patient(session, Encounter, patient_id)


def insert_note(session: Session, row):
    return _insert(session, Note, row)


def update_note(session: Session, row_id, fields):
    return _update(session, Note, row_id, fields)


def list_notes_by_patient(session: Session, patient_id):
    return _by_patient(session, Note, patient_id)


def search_notes(session: Session, patient_id, query):
    match = func.to_tsvector("english", Note.body).op("@@")(
        func.plainto_tsquery("english", query)
    )
    return _list_where(
        session,
        Note,
        Note.patient_id == _uuid(patient_id),
        match,
    )


def insert_document(session: Session, row):
    return _insert(session, Document, row)


def list_documents_by_patient(session: Session, patient_id):
    return _by_patient(session, Document, patient_id)


def insert_body_region(session: Session, row):
    return _insert(session, BodyRegion, row)


def get_body_region(session: Session, region_key):
    instance = session.get(BodyRegion, region_key)
    if instance is None:
        return None
    return _dump(instance)


def list_body_regions(session: Session):
    return _list_where(session, BodyRegion)


def insert_specialty_focus(session: Session, row):
    return _insert(session, SpecialtyFocus, row)


def list_specialty_focus(session: Session, specialty_key):
    return _list_where(
        session,
        SpecialtyFocus,
        SpecialtyFocus.specialty_key == specialty_key,
    )


def insert_reminder_rule(session: Session, row):
    return _insert(session, ReminderRule, row)


def list_reminder_rules(session: Session):
    return _list_where(session, ReminderRule)


def insert_reminder(session: Session, row):
    return _insert(session, Reminder, row)


def update_reminder(session: Session, row_id, fields):
    return _update(session, Reminder, row_id, fields)


def get_reminder(session: Session, reminder_id):
    return _get(session, Reminder, reminder_id)


def list_reminders_by_patient(session: Session, patient_id):
    return _by_patient(session, Reminder, patient_id)


def insert_request(session: Session, row):
    return _insert(session, Request, row)


def get_request(session: Session, request_id):
    return _get(session, Request, request_id)


def insert_suggestion(session: Session, row):
    return _insert(session, Suggestion, row)


def update_suggestion(session: Session, row_id, fields):
    return _update(session, Suggestion, row_id, fields)


def get_suggestion(session: Session, suggestion_id):
    return _get(session, Suggestion, suggestion_id)


def list_suggestions(session: Session, patient_id, status=None):
    criteria = [Suggestion.patient_id == _uuid(patient_id)]
    if status is not None:
        criteria.append(Suggestion.status == status)
    return _list_where(session, Suggestion, *criteria)


def insert_audit_log(session: Session, row):
    return _insert(session, AuditLog, row)


def list_audit_logs_by_patient(session: Session, patient_id):
    return _by_patient(session, AuditLog, patient_id)


def insert_sms_message(session: Session, row):
    return _insert(session, SmsMessage, row)


def update_sms_message(session: Session, row_id, fields):
    return _update(session, SmsMessage, row_id, fields)


def get_sms_message_by_sid(session: Session, twilio_sid):
    return _first_where(session, SmsMessage, SmsMessage.twilio_sid == twilio_sid)


def insert_coverage(session: Session, row):
    return _insert(session, Coverage, row)


def get_coverage_by_patient(session: Session, patient_id):
    return _first_where(session, Coverage, Coverage.patient_id == _uuid(patient_id))


def insert_eligibility_check(session: Session, row):
    return _insert(session, EligibilityCheck, row)


def list_eligibility_checks_by_patient(session: Session, patient_id):
    return _by_patient(session, EligibilityCheck, patient_id)


def insert_appointment(session: Session, row):
    return _insert(session, Appointment, row)


def update_appointment(session: Session, row_id, fields):
    return _update(session, Appointment, row_id, fields)


def get_appointment(session: Session, appointment_id):
    return _get(session, Appointment, appointment_id)


def list_appointments_by_patient(session: Session, patient_id):
    return _by_patient(session, Appointment, patient_id)


def list_appointments_on(session: Session, on: date):
    # starts_at is timestamptz. Compare instants against that UTC calendar day.
    start = datetime(on.year, on.month, on.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return _list_where(
        session,
        Appointment,
        Appointment.starts_at >= start,
        Appointment.starts_at < end,
    )
