from datetime import date, datetime, timezone
import math
from uuid import uuid4

from app.db.repositories import (
    get_suggestion,
    insert_audit_log,
    insert_note,
    insert_condition,
    insert_medication,
    insert_family_history,
    insert_observation,
    insert_reminder,
    list_body_regions,
    list_conditions_by_patient,
    list_medications_by_patient,
    list_family_history_by_patient,
    list_observations_by_patient,
    list_reminders_by_patient,
    list_reminder_rules,
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
    from app.integrations import embed_text as generate_embedding
    return generate_embedding(text)


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
    if not _writes_note(suggestion) and suggestion.get("target_id") is None:
        required = {
            "conditions": {"name", "status", "onset_date", "body_region_key"},
            "medications": {"name", "dose", "route", "frequency", "status", "start_date", "body_region_key"},
            "family_history": {"relationship", "condition", "age_at_diagnosis"},
            "observations": {"name", "value", "unit", "observed_at"},
            "reminder_schedule": {"name", "due_on", "status"},
        }[target_table]
        if any(after.get(key) is None for key in required):
            return _error("validation_error", "A new record proposal is missing required fields. Review and draft it again.")
    if not after or any(value is None for value in after.values()):
        return _error("validation_error", "Proposed fields must have recorded values.")
    for key, value in after.items():
        if key not in {"value", "age_at_diagnosis", "onset_date", "start_date", "due_on", "observed_at"} and (not isinstance(value, str) or not value.strip()):
            return _error("validation_error", "Text fields must contain nonempty text.")
    if "value" in after and (type(after["value"]) not in {int, float} or not math.isfinite(after["value"])):
        return _error("validation_error", "A measurement must be a finite number.")
    if "age_at_diagnosis" in after and (type(after["age_at_diagnosis"]) is not int or after["age_at_diagnosis"] < 0):
        return _error("validation_error", "Age at diagnosis must be a nonnegative whole number.")
    try:
        converted = _write_fields(target_table, after)
        for key in ("onset_date", "start_date", "due_on"):
            if key in converted and not isinstance(converted[key], date):
                raise ValueError("Invalid date")
        if "observed_at" in converted and not isinstance(converted["observed_at"], datetime):
            raise ValueError("Invalid timestamp")
    except (TypeError, ValueError):
        return _error("validation_error", "Review the proposed dates and timestamps before approval.")
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


def _matches_snapshot(table, target, before):
    # API timestamps use ISO 8601; database rows contain Python datetimes.
    # Compare the recorded instant, not its serialized spelling.
    try:
        expected = _write_fields(table, before)
        actual = _write_fields(table, {key: target.get(key) for key in before})
    except (TypeError, ValueError):
        return False
    for key, value in expected.items():
        recorded = actual[key]
        if isinstance(value, (date, datetime)) or key in {"value", "age_at_diagnosis"}:
            if recorded != value:
                return False
        elif str(recorded) != str(value):
            return False
    return True


_INSERTS = {"conditions": insert_condition, "medications": insert_medication, "family_history": insert_family_history, "observations": insert_observation, "reminder_schedule": insert_reminder}
_LISTS = {"conditions": list_conditions_by_patient, "medications": list_medications_by_patient, "family_history": list_family_history_by_patient, "observations": list_observations_by_patient, "reminder_schedule": list_reminders_by_patient}


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
        table = suggestion["target_table"]
        fields = _write_fields(table, after)
        fields.update(id=str(uuid4()), patient_id=suggestion["patient_id"])
        if table == "observations":
            fields.update(source=suggestion["source"], document_id=None)
            if suggestion["source"] == "lab_report":
                # Each extraction citation points to the stored original document.
                for citation in suggestion.get("citations") or []:
                    if citation.get("locator", "").startswith("document:"):
                        fields["document_id"] = citation["locator"].split(":", 1)[1]
                        break
            if not fields.get("body_region_key"):
                # General measurements have no inferred organ attribution.
                from app.db.repositories import insert_body_region
                regions = {r["region_key"] for r in list_body_regions(session)}
                if "general" not in regions:
                    insert_body_region(session, {"region_key": "general", "display_name": "General measurements", "mesh_name": ""})
                fields["body_region_key"] = "general"
        if table == "reminder_schedule":
            fields["rule_id"] = _rule_for(session, suggestion, after)["id"]
        _INSERTS[table](session, fields)
        return
    updater = _UPDATERS[suggestion["target_table"]]
    updater(session, target_id, _write_fields(suggestion["target_table"], after))


def _rule_for(session, suggestion, after):
    sources = {c.get("source_id") for c in suggestion.get("citations", [])}
    return next((r for r in list_reminder_rules(session) if r["name"].casefold() == after.get("name", "").casefold() or r["guideline_source_id"] in sources), None)


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
    for suggestion, after in planned:
        table = suggestion["target_table"]
        if "body_region_key" in after and after["body_region_key"] not in {r["region_key"] for r in list_body_regions(session)}:
            return _error("validation_error", "The proposed body region is not recorded.")
        if table == "reminder_schedule" and suggestion.get("target_id") is None and _rule_for(session, suggestion, after) is None:
            return _error("validation_error", "A new reminder must match a recorded screening rule.")
        if not _writes_note(suggestion) and suggestion.get("target_id") is not None:
            target = next((r for r in _LISTS[table](session, suggestion["patient_id"]) if str(r["id"]) == str(suggestion["target_id"])), None)
            if target is None:
                return _error("invalid_state", "The target record does not belong to this patient.")
            if not _matches_snapshot(table, target, suggestion.get("before", {})):
                return _error("invalid_state", "The record changed after this proposal was drafted. Review a new proposal.")
    from app.privacy.names import bind_patient_name, display_name_for

    approved = []
    with bind_patient_name(display_name_for(session, next(iter(patient_ids)))):
        for suggestion, after in planned:
            _apply_chart(session, suggestion, after)
            updated = update_suggestion(session, suggestion["id"], {"status": "approved"})
            _audit(session, suggestion, "approved", "Approved suggestion.")
            approved.append(updated)
    session.flush()
    return {
        "approved": approved,
        # Preserve the response contract without launching an unsolicited review.
        "reminder_review": {"suggestions": [], "answer": None},
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
