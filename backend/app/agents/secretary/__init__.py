"""Secretary chat. Answer insurance questions without writing the chart."""

import re
import uuid
from datetime import datetime, timezone

# Patient ids, member ids, phones, and full dates. Ages and bare years stay.
_IDENTIFIER = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|NW-\d+"
    r"|\+\d{10,15}"
    r"|(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)"
    r"|(?<!\d)\d{1,2}/\d{1,2}/\d{4}(?!\d)"
    r"|(?i:\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\b\.?\s+\d{1,2}(?:st|nd|rd|th)?,\s*\d{4}\b)"
)


def _search_text(text):
    """Leave clean search text unchanged. Strip identifiers and full dates."""
    if not isinstance(text, str) or _IDENTIFIER.search(text) is None:
        return text
    return " ".join(_IDENTIFIER.sub(" ", text).split())


def _execute_tool(call, patient_id, session, tools, evidence):
    name = call.get("name") if isinstance(call, dict) else None
    if name == "get_coverage":
        tools.get_coverage(patient_id, session=session)
    elif name == "search_payer_docs":
        evidence.search_payer_docs(_search_text(call.get("text", "")))
    elif name == "web_search":
        evidence.web_search(_search_text(call.get("text", "")))


def answer_secretary(patient_id, text, *, session):
    import app.agents.secretary.model as model
    import app.evidence as evidence
    import app.mcp.tools as tools
    from app.db.repositories import insert_request

    response = model.complete("secretary", {"text": text, "coverage": tools.get_coverage(patient_id, session=session)})
    for call in response.get("tool_calls") or []:
        _execute_tool(call, patient_id, session, tools, evidence)

    stored = insert_request(
        session,
        {
            "id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "channel": "typed",
            "role": "secretary",
            "transcript": text,
            "route": "secretary",
            "created_at": datetime.now(timezone.utc),
        },
    )
    answer = response["answer"]
    return {
        "request_id": stored["id"],
        "answer": {"text": answer["text"], "citations": answer["citations"]},
    }
