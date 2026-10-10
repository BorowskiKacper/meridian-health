"""Coverage answers grounded in the actual payer passages and recorded coverage."""

from pydantic import BaseModel

from app.integrations import gemini_json, IntegrationError
from app.agents.doctor.model import _BASE, _query, _ground_citations, Answer


class SecretaryAnswer(BaseModel):
    answer: Answer


def complete(task, payload):
    if task != "secretary":
        raise ValueError("Unsupported secretary task")
    import app.evidence as evidence
    query = _query({"text": payload["text"]})
    try:
        passages = evidence.search_payer_docs(query)["passages"]
    except Exception:
        raise IntegrationError("Snowflake", "The payer document search could not finish. Check the Snowflake configuration and try again.") from None
    result = gemini_json(_BASE + "Answer this administrative question using the supplied coverage and payer documents. Do not offer clinical advice, write chart changes, claim real-time insurer verification, or fabricate benefits. Cite only supplied payer passages. If coverage is missing say so.", {**payload, "evidence": passages}, SecretaryAnswer).model_dump()
    result["answer"]["citations"] = _ground_citations(result["answer"]["citations"], passages)
    return {**result, "tool_calls": []}
