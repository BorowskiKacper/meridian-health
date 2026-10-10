from datetime import date, datetime, timezone
from uuid import uuid4

from app.db.repositories import (
    get_suggestion,
    insert_audit_log,
    insert_note,
    insert_suggestion,
    list_suggestions as list_stored_suggestions,
    update_condition,
    update_family_history,
    update_medication,
    update_observation,
    update_reminder,
    update_suggestion,
)
from app.schemas import Suggestion

_ALLOWLIST = {
    "conditions": frozenset({"name", "status", "onset_date", "body_region_key"}),
    "medications": frozenset(
        {
            "name",
            "dose",
            "route",
            "frequency",
            "status",
            "start_date",
            "body_region_key",
        }
    ),
    "family_history": frozenset({"relationship", "condition", "age_at_diagnosis"}),
    "observations": frozenset(
        {"name", "value", "unit", "observed_at", "body_region_key"}
    ),
    "notes": frozenset({"body"}),
    "reminder_schedule": frozenset({"name", "due_on", "status"}),
}

_STATUS_VALUES = {
    "conditions": frozenset({"active", "resolved", "controlled"}),
    "medications": frozenset({"active", "stopped"}),
    "reminder_schedule": frozenset({"scheduled", "paused", "sent", "done"}),
}

_UPDATERS = {
    "conditions": update_condition,
    "medications": update_medication,
    "family_history": update_family_history,
    "observations": update_observation,
    "reminder_schedule": update_reminder,
}

_DATE_FIELDS = {
    "conditions": "onset_date",
    "medications": "start_date",
    "reminder_schedule": "due_on",
}


def embed_text(text):
    return [0.0 for _ in range(768)] if text is not None else [0.0] * 768


def _error(code, message):
    return {"error": {"code": code, "message": message}}


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return value


def _as_datetime(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return value


def _get_stored_suggestion(session, suggestion_id):
    try:
        return get_suggestion(session, suggestion_id)
    except (TypeError, ValueError):
        return None


def _load_pending(ids, session):
    rows = []
    for suggestion_id in ids:
        stored = _get_stored_suggestion(session, suggestion_id)
        if stored is None or stored["status"] != "pending":
            return None, _error(
                "invalid_state",
                "Suggestion is missing or is not pending.",
            )
        rows.append(stored)
    return rows, None


def _edit_entry(edits, suggestion_id):
    if not edits:
        return None
    if suggestion_id in edits:
        return edits[suggestion_id]
    wanted = str(suggestion_id)
    for key, value in edits.items():
        if str(key) == wanted:
            return value
    return None


def _writes_note(suggestion):
    return (
        suggestion["kind"] in {"soap_note", "plan_item"}
        or suggestion["target_table"] == "notes"
    )


def _effective_after(suggestion, edits):
    entry = _edit_entry(edits, suggestion["id"])
    if entry is None:
        after = suggestion["after"]
        if not isinstance(after, dict):
            return None, _error("validation_error", "Suggestion after must be an object.")
        return after, None
    if not isinstance(entry, dict) or not isinstance(entry.get("after"), dict):
        return None, _error("validation_error", "Each edit must include an after object.")
    return entry["after"], None


def _validate_after(suggestion, after):
    target_table = suggestion["target_table"]
    allowed = _ALLOWLIST.get(target_table)
    if allowed is None:
        return _error("validation_error", "Target table is not allowlisted.")
    unknown = sorted(set(after) - allowed)
    if unknown:
        names = ", ".join(unknown)
        return _error(
            "validation_error",
            f"Fields not allowed for {target_table}: {names}.",
        )
    statuses = _STATUS_VALUES.get(target_table)
    if statuses is not None and "status" in after and after["status"] not in statuses:
        allowed_status = ", ".join(sorted(statuses))
        return _error(
            "validation_error",
            f"Status must be one of: {allowed_status}.",
        )
    if _writes_note(suggestion) and not isinstance(after.get("body"), str):
        return _error("validation_error", "A note suggestion requires after.body.")
    return None


def _plan_writes(rows, edits):
    if edits is not None and not isinstance(edits, dict):
        return None, _error("validation_error", "Edits must be an object.")
    planned = []
    for suggestion in rows:
        after, error = _effective_after(suggestion, edits)
        if error is not None:
            return None, error
        error = _validate_after(suggestion, after)
        if error is not None:
            return None, error
        planned.append((suggestion, after))
    return planned, None


def _write_fields(target_table, after):
    fields = dict(after)
    date_key = _DATE_FIELDS.get(target_table)
    if date_key is not None and date_key in fields:
        fields[date_key] = _as_date(fields[date_key])
    if target_table == "observations" and "observed_at" in fields:
        fields["observed_at"] = _as_datetime(fields["observed_at"])
    return fields


def _apply_chart(session, suggestion, after):
    if _writes_note(suggestion):
        body = after["body"]
        embedding = embed_text(body)
        insert_note(
            session,
            {
                "id": str(uuid4()),
                "patient_id": suggestion["patient_id"],
                "body": body,
                "embedding": embedding,
                "source_suggestion_id": suggestion["id"],
                "created_at": datetime.now(timezone.utc),
            },
        )
        return
    target_id = suggestion.get("target_id")
    if target_id is None:
        return
    updater = _UPDATERS[suggestion["target_table"]]
    updater(session, target_id, _write_fields(suggestion["target_table"], after))


def _audit(session, suggestion, action, detail):
    insert_audit_log(
        session,
        {
            "id": str(uuid4()),
            "patient_id": suggestion["patient_id"],
            "suggestion_id": suggestion["id"],
            "action": action,
            "detail": detail,
            "created_at": datetime.now(timezone.utc),
        },
    )


def approve_suggestions(ids, edits, *, session):
    rows, error = _load_pending(ids, session)
    if error is not None:
        return error
    if not rows:
        return _error("invalid_state", "No suggestions to approve.")
    patient_ids = {str(row["patient_id"]) for row in rows}
    if len(patient_ids) != 1:
        return _error("invalid_state", "Suggestions must belong to one patient.")
    planned, error = _plan_writes(rows, edits)
    if error is not None:
        return error
    approved = []
    for suggestion, after in planned:
        _apply_chart(session, suggestion, after)
        updated = update_suggestion(session, suggestion["id"], {"status": "approved"})
        _audit(session, suggestion, "approved", "Approved suggestion.")
        approved.append(updated)
    session.flush()
    import app.agents.doctor as doctor

    review = doctor.run_reminder_agent(
        rows[0]["patient_id"],
        "post_approval",
        session=session,
    )
    return {
        "approved": approved,
        "reminder_review": {
            "suggestions": review["suggestions"],
            "answer": review["answer"],
        },
    }


def reject_suggestions(ids, reason, *, session):
    rows, error = _load_pending(ids, session)
    if error is not None:
        return error
    rejected = []
    for suggestion in rows:
        updated = update_suggestion(session, suggestion["id"], {"status": "rejected"})
        _audit(session, suggestion, "rejected", reason)
        rejected.append(updated)
    return {"rejected": rejected}


def list_suggestions(patient_id, status, *, session):
    selected = "pending" if status is None else status
    return {"suggestions": list_stored_suggestions(session, patient_id, selected)}


def create_plan_item(patient_id, request_id, text, citations, *, session):
    row = {
        "id": str(uuid4()),
        "patient_id": patient_id,
        "request_id": request_id,
        "kind": "plan_item",
        "status": "pending",
        "target_table": "notes",
        "target_id": None,
        "before": {},
        "after": {"body": text},
        "reason": text,
        "confidence": 1.0,
        "citations": citations,
        "validation_flags": [],
        "source": "research_add_to_plan",
    }
    Suggestion.model_validate(row)
    return insert_suggestion(session, row)
