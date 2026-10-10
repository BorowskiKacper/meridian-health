"""Eligibility checks from seeded coverage and payer documents."""

import json
import uuid
from datetime import datetime, timezone

import app.evidence as evidence
from app.db.repositories import (
    get_coverage_by_patient,
    get_patient,
    insert_eligibility_check,
)

_NOT_FOUND = "not_found"


def ask_model(prompt):
    """Ask Gemini for a coverage summary and a prior-auth decision.

    Returns summary, prior_auth_required, and prior_auth_note.
    """
    from google import genai
    from google.genai import types

    from app import config

    client = genai.Client(api_key=config.GEMINI_API_KEY, http_options={"timeout": 90000, "retry_options": {"attempts": 1}})
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "summary": {"type": "STRING"},
                    "prior_auth_required": {"type": "BOOLEAN"},
                    "prior_auth_note": {"type": "STRING"},
                },
                "required": [
                    "summary",
                    "prior_auth_required",
                    "prior_auth_note",
                ],
            },
        ),
    )
    payload = json.loads(response.text or "{}")
    note = payload.get("prior_auth_note") or ""
    return {
        "summary": payload.get("summary") or "",
        "prior_auth_required": bool(payload.get("prior_auth_required")),
        "prior_auth_note": note if isinstance(note, str) else "",
    }


def _not_found(message):
    return {"error": {"code": _NOT_FOUND, "message": message}}


def _coverage_view(coverage):
    return {
        "payer_name": coverage["payer_name"],
        "member_id": coverage["member_id"],
        "plan_name": coverage["plan_name"],
        "active": coverage["active"],
        "deductible_remaining": coverage["deductible_remaining"],
        "copay": coverage["copay"],
        "benefits": coverage["benefits"],
    }


def _stored_order_text(order_text):
    if not isinstance(order_text, str) or order_text.strip() == "":
        return ""
    return order_text


def _prompt(coverage, order_text):
    benefits = []
    for item in coverage["benefits"] or []:
        benefits.append({"name": item["name"], "detail": item["detail"]})
    payload = {
        "payer_name": coverage["payer_name"],
        "plan_name": coverage["plan_name"],
        "active": coverage["active"],
        "deductible_remaining": coverage["deductible_remaining"],
        "copay": coverage["copay"],
        "benefits": benefits,
        "order_text": order_text,
    }
    return (
        "Summarize this insurance coverage in plain English and decide whether "
        "the order needs prior authorization. Use only the fields in this JSON. "
        "Reply with summary, prior_auth_required, and prior_auth_note.\n"
        + json.dumps(payload)
    )


def check_eligibility(patient_id, order_text, *, session):
    patient = get_patient(session, patient_id)
    if patient is None:
        return _not_found("Patient was not found.")

    coverage = get_coverage_by_patient(session, patient_id)
    if coverage is None:
        return _not_found("Coverage was not found.")

    stored_order = _stored_order_text(order_text)
    decision = ask_model(_prompt(coverage, stored_order))
    summary = decision["summary"]
    prior_auth = None
    prior_auth_note = ""
    citations = []

    if stored_order and decision["prior_auth_required"] is True:
        found = evidence.search_payer_docs(stored_order)
        citations = list(found["passages"])
        prior_auth_note = decision["prior_auth_note"] or ""
        prior_auth = {"note": prior_auth_note, "citations": citations}

    insert_eligibility_check(
        session,
        {
            "id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "coverage_id": coverage["id"],
            "order_text": stored_order,
            "summary": summary,
            "prior_auth_note": prior_auth_note,
            "citations": citations,
            "created_at": datetime.now(timezone.utc),
        },
    )
    return {
        "coverage": _coverage_view(coverage),
        "summary": summary,
        "prior_auth": prior_auth,
    }
