"""Patient context tools agents call instead of querying the database."""

import uuid
from datetime import date, datetime, timezone

from pydantic import ValidationError

from app.db.repositories import (
    get_coverage_by_patient,
    get_patient,
    insert_suggestion,
    list_allergies_by_patient,
    list_conditions_by_patient,
    list_encounters_by_patient,
    list_family_history_by_patient,
    list_medications_by_patient,
    list_observations_by_patient,
    list_reminders_by_patient,
    list_suggestions,
    search_notes,
)
from app.schemas import Suggestion

_DATE_FIELDS = ("onset_date", "start_date", "due_on", "recorded_on")
_TIMESTAMP_FIELDS = ("observed_at", "occurred_at")
_COVERAGE_FIELDS = (
    "payer_name",
    "member_id",
    "plan_name",
    "active",
    "deductible_remaining",
    "copay",
    "benefits",
)


def preview_request_route(patient_id, text, *, session):
    """Read-only workflow selection; never draft or execute a chart action."""
    try:
        patient = get_patient(session, patient_id)
    except ValueError:
        patient = None
    if patient is None:
        return _error("not_found", "Patient was not found.")
    if not isinstance(text, str) or not text.strip():
        return _error("validation_error", "A nonempty request or recognized transcript is required.")
    from app.agents.doctor.model import complete
    from app.privacy.names import bind_patient_name
    with bind_patient_name(patient.get("display_name")):
        route = complete("classify", {"text": text})["route"]
    descriptions = {
        "chart_update": "Draft proposed chart changes for your review.",
        "clinical_question": "Research a clinical question using the patient chart and evidence.",
        "check_screenings": "Review screening needs and propose follow-up changes. No messages will be sent.",
    }
    return {"route": route, "transcript": text, "description": descriptions[route]}


def get_patient_context(patient_id, *, session):
    patient = get_patient(session, patient_id)
    if patient is None:
        return _error("not_found", "Patient was not found.")
    encounters = list_encounters_by_patient(session, patient_id)
    pending = list_suggestions(session, patient_id, "pending")
    return {
        "patient_id": str(patient["id"]),
        "age": _age(patient["date_of_birth"]),
        "allergies": _rows(list_allergies_by_patient(session, patient_id)),
        "conditions": _rows(list_conditions_by_patient(session, patient_id)),
        "medications": _rows(list_medications_by_patient(session, patient_id)),
        "recent_observations": _rows(list_observations_by_patient(session, patient_id)),
        "family_history": _rows(list_family_history_by_patient(session, patient_id)),
        "past_procedures": [
            _chart_row(row)
            for row in encounters
            if row.get("encounter_type") == "procedure"
        ],
        "reminders": _rows(list_reminders_by_patient(session, patient_id)),
        "pending_suggestions": [_pending_suggestion(row) for row in pending],
    }


def search_patient_notes(patient_id, query, *, session):
    observations = list_observations_by_patient(session, patient_id)
    notes = []
    for note in search_notes(session, patient_id, query):
        excerpt = note["body"]
        notes.append(
            {
                "id": str(note["id"]),
                "excerpt": excerpt,
                "observed_labs": _observed_labs(observations, query, excerpt),
            }
        )
    return {"notes": notes}


def get_coverage(patient_id, *, session):
    row = get_coverage_by_patient(session, patient_id)
    if row is None:
        return _error("not_found", "Coverage was not found.")
    return {key: row[key] for key in _COVERAGE_FIELDS}


def propose_change(patient_id, suggestion, *, session):
    payload = dict(suggestion)
    payload["id"] = str(uuid.uuid4())
    payload["patient_id"] = patient_id
    payload["status"] = "pending"
    try:
        validated = Suggestion.model_validate(payload)
    except ValidationError as exc:
        return _error("validation_error", _validation_message(exc))
    if any(citation.tier == "web" for citation in validated.citations):
        return _error("validation_error", "Suggestions cannot cite a web source.")
    if validated.kind == "reminder_change" and not any(
        citation.tier == "baseline" for citation in validated.citations
    ):
        return _error(
            "validation_error",
            "A reminder change must cite a baseline source.",
        )
    row = validated.model_dump(exclude={"unconfirmed"})
    return insert_suggestion(session, row)


def _error(code, message):
    return {"error": {"code": code, "message": message}}


def _validation_message(exc):
    text = str(exc).strip()
    if text:
        return text
    return "Suggestion is not valid."


def _age(dob):
    born = _as_date(dob)
    today = datetime.now(timezone.utc).date()
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return int(years)


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _date_string(value):
    if value is None:
        return None
    return _as_date(value).isoformat()


def _timestamp(value):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z") and "." not in text:
            return text
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        value = datetime.fromisoformat(text)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return value


def _chart_row(row):
    copied = dict(row)
    for key in _DATE_FIELDS:
        if key in copied:
            copied[key] = _date_string(copied[key])
    for key in _TIMESTAMP_FIELDS:
        if key in copied:
            copied[key] = _timestamp(copied[key])
    return copied


def _rows(rows):
    return [_chart_row(row) for row in rows]


def _pending_suggestion(row):
    item = _chart_row(row)
    item["unconfirmed"] = True
    return item


def _observed_labs(observations, query, excerpt):
    labs = []
    for observation in observations:
        name = observation["name"]
        if name not in query and name not in excerpt:
            continue
        labs.append(
            {
                "id": str(observation["id"]),
                "name": name,
                "value": observation["value"],
                "unit": observation["unit"],
                "observed_at": _timestamp(observation["observed_at"]),
            }
        )
    return labs
