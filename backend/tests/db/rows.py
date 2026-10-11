from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

UTC = timezone.utc
CREATED_AT = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)

_email_suffix = 200


def new_id():
    return str(uuid4())


def _email():
    global _email_suffix
    _email_suffix += 1
    return f"patient{_email_suffix}@example.com"


def citation():
    return {
        "source_id": "uspstf:colorectal-cancer-screening",
        "title": "Colorectal Cancer: Screening",
        "passage": "Screen adults aged 45 to 49 years for colorectal cancer.",
        "locator": (
            "https://www.uspreventiveservicestaskforce.org/uspstf/"
            "recommendation/colorectal-cancer-screening"
        ),
        "tier": "baseline",
    }


def embedding768():
    return [0.0 if index % 2 == 0 else 0.5 for index in range(768)]


def patient_row(**overrides):
    row = {
        "id": new_id(),
        "display_name": "Ada Lovelace",
        "date_of_birth": date(1815, 12, 10),
        "sex": "female",
        "email_opt_in": True,
        "email": _email(),
    }
    row.update(overrides)
    return row


def condition_row(patient_id, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "name": "Hypertension",
        "status": "active",
        "onset_date": date(2019, 4, 1),
        "body_region_key": "heart",
    }
    row.update(overrides)
    return row


def medication_row(patient_id, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "name": "Lisinopril",
        "dose": "10 mg",
        "route": "oral",
        "frequency": "daily",
        "status": "active",
        "start_date": date(2019, 4, 2),
        "body_region_key": "heart",
    }
    row.update(overrides)
    return row


def family_history_row(patient_id, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "relationship": "father",
        "condition": "colorectal cancer",
        "age_at_diagnosis": 48,
    }
    row.update(overrides)
    return row


def observation_row(patient_id, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "name": "LDL",
        "value": 140,
        "unit": "mg/dL",
        "observed_at": datetime(2024, 3, 1, tzinfo=UTC),
        "source": "lab_report",
        "document_id": None,
        "body_region_key": "heart",
    }
    row.update(overrides)
    return row


def encounter_row(patient_id, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "encounter_type": "office",
        "occurred_at": CREATED_AT,
        "summary": "Office visit for blood pressure.",
    }
    row.update(overrides)
    return row


def note_row(patient_id, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "body": "The LDL result is high.",
        "embedding": None,
        "source_suggestion_id": None,
        "created_at": CREATED_AT,
    }
    row.update(overrides)
    return row


def document_row(patient_id, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "storage_key": f"labs/{patient_id}/ldl.pdf",
        "media_type": "application/pdf",
        "uploaded_at": CREATED_AT,
    }
    row.update(overrides)
    return row


def body_region_row(region_key, display_name, mesh_name):
    return {
        "region_key": region_key,
        "display_name": display_name,
        "mesh_name": mesh_name,
    }


def specialty_focus_row(specialty_key, region_key):
    return {"specialty_key": specialty_key, "region_key": region_key}


def reminder_rule_row(**overrides):
    row = {
        "id": new_id(),
        "name": "Colorectal cancer screening",
        "baseline_age": 45,
        "guideline_source_id": "uspstf:colorectal-cancer-screening",
    }
    row.update(overrides)
    return row


def reminder_row(patient_id, rule_id, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "rule_id": rule_id,
        "name": "Colorectal cancer screening",
        "due_on": date(2026, 10, 1),
        "status": "scheduled",
    }
    row.update(overrides)
    return row


def request_row(patient_id, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "channel": "typed",
        "role": "doctor",
        "transcript": "Update the chart from today's visit.",
        "route": "chart_update",
        "created_at": CREATED_AT,
    }
    row.update(overrides)
    return row


def suggestion_row(patient_id, request_id, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "request_id": request_id,
        "kind": "field_update",
        "status": "pending",
        "target_table": "conditions",
        "target_id": None,
        "before": {"status": "active"},
        "after": {"status": "controlled"},
        "reason": "Recent readings show the condition is controlled.",
        "confidence": 0.5,
        "citations": [citation()],
        "validation_flags": ["low_confidence"],
        "source": "chart_agent",
    }
    row.update(overrides)
    return row


def audit_log_row(patient_id, suggestion_id, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "suggestion_id": suggestion_id,
        "action": "approve",
        "detail": "Doctor approved the suggestion.",
        "created_at": CREATED_AT,
    }
    row.update(overrides)
    return row


def email_message_row(patient_id, reminder_id, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "reminder_id": reminder_id,
        "to_email": "ada@example.com",
        "body": "You have a clinic reminder. Please contact the office to schedule a visit.",
        "provider_id": new_id(),
        "status": "queued",
    }
    row.update(overrides)
    return row


def coverage_row(patient_id, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "payer_name": "Northwind Health",
        "member_id": "NW-9000",
        "plan_name": "PPO",
        "active": True,
        "deductible_remaining": 400,
        "copay": 30,
        "benefits": [
            {"name": "Preventive colonoscopy", "detail": "Covered in network"}
        ],
    }
    row.update(overrides)
    return row


def eligibility_check_row(patient_id, coverage_id, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "coverage_id": coverage_id,
        "order_text": "colonoscopy",
        "summary": "Covered in network.",
        "prior_auth_note": "No prior authorization required.",
        "citations": [citation()],
        "created_at": CREATED_AT,
    }
    row.update(overrides)
    return row


def appointment_row(patient_id, starts_at, **overrides):
    row = {
        "id": new_id(),
        "patient_id": patient_id,
        "starts_at": starts_at,
        "ends_at": starts_at + timedelta(minutes=30),
        "reason": "Follow-up",
        "status": "scheduled",
    }
    row.update(overrides)
    return row
