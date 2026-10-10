"""Route a doctor request and run the reminder agent."""

import re
import uuid
from datetime import datetime, timezone

from app.agents.doctor.verify import verify_claims
from app.db.repositories import insert_request, list_reminder_rules

# Same identifier shapes the evidence guard rejects. Ages and bare years stay.
_IDENTIFIERS = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|NW-\d+"
    r"|\+\d{10,15}"
    r"|(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)"
    r"|(?<!\d)\d{1,2}/\d{1,2}/\d{4}(?!\d)"
    r"|(?i:\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\b\.?\s+\d{1,2}(?:st|nd|rd|th)?,\s*\d{4}\b)"
)

_TRUSTED_EVIDENCE = "Trusted evidence was not found."


def route_doctor_request(patient_id, text, channel, *, session):
    import app.agents.doctor.model as model

    classified = model.complete("classify", {"text": text})
    route = classified["route"]
    stored = insert_request(
        session,
        {
            "id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "channel": channel,
            "role": "doctor",
            "transcript": text,
            "route": route,
            "created_at": datetime.now(timezone.utc),
        },
    )
    suggestions = []
    answer = None
    spoken_text = None
    if route == "chart_update":
        suggestions = _chart_update(patient_id, text, session)
        if channel == "voice":
            spoken_text = _spoken_chart(suggestions)
    elif route == "clinical_question":
        answer = _research_answer(patient_id, text, session)
        if channel == "voice":
            spoken_text = _spoken_answer(answer)
    elif route == "check_screenings":
        review = run_reminder_agent(patient_id, "doctor_request", session=session)
        if review["suggestions"]:
            suggestions = review["suggestions"]
            if channel == "voice":
                spoken_text = _spoken_chart(suggestions)
        else:
            answer = {"text": review["answer"], "citations": []}
            if channel == "voice":
                spoken_text = _spoken_answer(answer)
    return {
        "request_id": stored["id"],
        "transcript": text,
        "route": route,
        "suggestions": suggestions,
        "answer": answer,
        "spoken_text": spoken_text,
        "audio_base64": None,
    }


def run_reminder_agent(patient_id, trigger, *, session):
    import app.agents.doctor.model as model
    import app.mcp.tools as tools

    context = tools.get_patient_context(patient_id, session=session)
    rules = list_reminder_rules(session)
    decision = model.complete(
        "reminders",
        {
            "trigger": trigger,
            "context": context,
            "rules": rules,
            "tool_calls": _requested_tool_calls(patient_id, "screening review"),
        },
    )
    _execute_tool_calls(patient_id, decision.get("tool_calls"), session)
    answer = decision.get("answer")
    if decision.get("up_to_date") is True:
        return {"suggestions": [], "answer": answer}

    stored = []
    for suggestion in decision.get("suggestions") or []:
        verified = verify_claims(
            suggestion.get("reason") or "",
            suggestion.get("citations") or [],
        )
        if not _has_tier(verified["citations"], "baseline"):
            continue
        proposal = dict(suggestion)
        proposal["reason"] = verified["text"]
        proposal["citations"] = verified["citations"]
        row = tools.propose_change(patient_id, proposal, session=session)
        if _is_pending(row):
            stored.append(row)
    return {"suggestions": stored, "answer": answer}


def _chart_update(patient_id, text, session):
    import app.agents.doctor.model as model
    import app.mcp.tools as tools

    context = tools.get_patient_context(patient_id, session=session)
    chart = model.complete("chart", {"text": text, "context": context})
    stored = []
    for suggestion in chart.get("suggestions") or []:
        row = tools.propose_change(patient_id, suggestion, session=session)
        if _is_pending(row):
            stored.append(row)
    return stored


def _research_answer(patient_id, text, session):
    import app.agents.doctor.model as model
    import app.mcp.tools as tools

    context = tools.get_patient_context(patient_id, session=session)
    notes = tools.search_patient_notes(patient_id, text, session=session)
    research = model.complete(
        "research",
        {
            "text": text,
            "context": context,
            "notes": notes,
            "tool_calls": _requested_tool_calls(
                patient_id,
                text,
                include_notes=True,
            ),
        },
    )
    _execute_tool_calls(patient_id, research.get("tool_calls"), session)
    body = research.get("answer") or {}
    verified = verify_claims(body.get("text") or "", body.get("citations") or [])
    if research.get("recommends_action") is True and not _has_tier(
        verified["citations"],
        "baseline",
        "guideline",
    ):
        return {"text": _TRUSTED_EVIDENCE, "citations": []}
    return {"text": verified["text"], "citations": verified["citations"]}


def _requested_tool_calls(patient_id, description, *, include_notes=False):
    leaked = f"{description} {patient_id}"
    calls = [
        {"name": "search_guidelines", "text": leaked, "corpus": "uspstf"},
        {"name": "search_guidelines", "text": leaked, "corpus": "pubmed"},
        {"name": "search_medical_web", "text": leaked},
    ]
    if include_notes:
        calls.append({"name": "search_patient_notes", "query": description})
    return calls


def _execute_tool_calls(patient_id, tool_calls, session):
    import app.evidence as evidence
    import app.mcp.tools as tools

    for call in tool_calls or []:
        if not isinstance(call, dict):
            continue
        name = call.get("name")
        if name == "search_guidelines":
            evidence.search_guidelines(
                _strip_identifiers(call.get("text")),
                call.get("corpus"),
            )
        elif name == "search_medical_web":
            evidence.search_medical_web(_strip_identifiers(call.get("text")))
        elif name == "search_patient_notes":
            tools.search_patient_notes(
                patient_id,
                call.get("query", ""),
                session=session,
            )


def _strip_identifiers(text):
    return _IDENTIFIERS.sub("", "" if text is None else str(text))


def _has_tier(citations, *tiers):
    wanted = set(tiers)
    return any(
        isinstance(item, dict) and item.get("tier") in wanted for item in citations or []
    )


def _is_pending(row):
    return isinstance(row, dict) and row.get("status") == "pending" and "id" in row


def _spoken_answer(answer):
    text = answer.get("text") if isinstance(answer, dict) else None
    if not isinstance(text, str) or not text.strip():
        return None
    return text


def _spoken_chart(suggestions):
    reasons = []
    for item in suggestions:
        reason = item.get("reason") if isinstance(item, dict) else None
        if isinstance(reason, str) and reason.strip():
            reasons.append(reason.strip())
    if reasons:
        return "I will propose these chart updates. " + " ".join(reasons)
    return "I will propose a chart update."
