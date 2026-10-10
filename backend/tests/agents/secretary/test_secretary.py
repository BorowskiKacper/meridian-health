import importlib
import sys
import types

from sqlalchemy import func, select

import app.mcp.tools as mcp_tools
from app.agents.secretary import answer_secretary
from app.db.models import Request
from app.db.repositories import (
    get_request,
    list_conditions_by_patient,
    list_suggestions,
)

JANE_ID = "11111111-1111-4111-8111-111111111111"
MEMBER_ID = "NW-1001"
PHONE = "+15555550101"
QUESTION = "Does this plan require prior authorization for a screening colonoscopy?"
ANSWER_TEXT = "This plan lists prior auth for the order."
PAYER_QUERY = "prior auth for a screening colonoscopy"
WEB_QUERY = "how insurers handle prior authorization appeals"

PAYER_CITATION = {
    "source_id": "payer-doc-colonoscopy-auth",
    "title": "Northwind prior authorization list",
    "passage": "Screening colonoscopy requires prior authorization.",
    "locator": "Northwind Health, Prior Authorization List",
    "tier": "payer",
}
WEB_CITATION = {
    "source_id": "web-prior-auth-appeals",
    "title": "Prior authorization appeals",
    "passage": "Insurers publish steps for appealing a prior authorization denial.",
    "locator": "https://example.com/insurer-prior-auth-appeals",
    "tier": "web",
}
MODEL_CITATIONS = [PAYER_CITATION, WEB_CITATION]


def invoke(fn, *args, session, **kwargs):
    import inspect

    if "session" in inspect.signature(fn).parameters:
        kwargs["session"] = session
    return fn(*args, **kwargs)


def _request_count(session):
    return session.scalar(select(func.count()).select_from(Request))


def _patient_id(args, kwargs):
    if "patient_id" in kwargs:
        return str(kwargs["patient_id"])
    assert args
    return str(args[0])


def _text_arg(args, kwargs):
    if "text" in kwargs:
        return kwargs["text"]
    assert args
    return args[0]


def _secretary_model():
    name = "app.agents.secretary.model"
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        module = types.ModuleType(name)
        module.__package__ = "app.agents.secretary"
        sys.modules[name] = module
        import app.agents.secretary as secretary

        secretary.model = module
        return module


def _install(monkeypatch):
    coverage_calls = []
    payer_calls = []
    web_calls = []
    propose_calls = []
    real_get_coverage = mcp_tools.get_coverage

    def get_coverage(*args, **kwargs):
        coverage_calls.append((args, kwargs))
        return real_get_coverage(*args, **kwargs)

    def search_payer_docs(*args, **kwargs):
        payer_calls.append((args, kwargs))
        return {"passages": [dict(PAYER_CITATION)]}

    def web_search(*args, **kwargs):
        web_calls.append((args, kwargs))
        return {
            "text": "Insurers publish appeal steps for prior authorization.",
            "citations": [dict(WEB_CITATION)],
        }

    def propose_change(*args, **kwargs):
        propose_calls.append((args, kwargs))
        raise AssertionError("propose_change must not be called")

    def complete(task, payload):
        if task != "secretary" or payload is None:
            raise AssertionError("complete was not called for the secretary task")
        return {
            "tool_calls": [
                {"name": "get_coverage"},
                {"name": "search_payer_docs", "text": PAYER_QUERY},
                {"name": "web_search", "text": WEB_QUERY},
                {"name": "propose_change"},
            ],
            "answer": {
                "text": ANSWER_TEXT,
                "citations": [dict(citation) for citation in MODEL_CITATIONS],
            },
        }

    _secretary_model()
    monkeypatch.setattr(
        "app.agents.secretary.model.complete",
        complete,
        raising=False,
    )
    monkeypatch.setattr("app.mcp.tools.get_coverage", get_coverage)
    monkeypatch.setattr("app.evidence.search_payer_docs", search_payer_docs)
    monkeypatch.setattr("app.evidence.web_search", web_search)
    monkeypatch.setattr("app.mcp.tools.propose_change", propose_change)
    return coverage_calls, payer_calls, web_calls, propose_calls


def test_secretary_chat_stores_request_and_does_not_write_the_chart(
    seeded_db, monkeypatch
):
    session = seeded_db.session
    conditions_before = list_conditions_by_patient(session, JANE_ID)
    suggestions_before = list_suggestions(session, JANE_ID)
    requests_before = _request_count(session)
    coverage_calls, payer_calls, web_calls, propose_calls = _install(monkeypatch)

    result = invoke(answer_secretary, JANE_ID, QUESTION, session=session)

    assert isinstance(result, dict)
    assert set(result) == {"request_id", "answer"}
    assert "suggestions" not in result
    answer = result["answer"]
    assert isinstance(answer, dict)
    assert set(answer) == {"text", "citations"}
    assert answer["text"] == ANSWER_TEXT
    assert answer["citations"] == MODEL_CITATIONS
    for citation in answer["citations"]:
        assert set(citation) == {"source_id", "title", "passage", "locator", "tier"}
    assert [citation["tier"] for citation in answer["citations"]] == ["payer", "web"]

    assert _request_count(session) == requests_before + 1
    row = get_request(session, result["request_id"])
    assert row["id"] == str(result["request_id"])
    assert row["patient_id"] == JANE_ID
    assert row["role"] == "secretary"
    assert row["route"] == "secretary"
    assert row["channel"] == "typed"
    assert row["transcript"] == QUESTION

    assert coverage_calls
    assert {_patient_id(args, kwargs) for args, kwargs in coverage_calls} == {JANE_ID}

    assert payer_calls
    for args, kwargs in payer_calls:
        text = _text_arg(args, kwargs)
        assert isinstance(text, str)
        assert JANE_ID not in text
        assert MEMBER_ID not in text
        assert PHONE not in text

    assert web_calls
    assert propose_calls == []
    assert list_suggestions(session, JANE_ID) == suggestions_before == []
    assert list_conditions_by_patient(session, JANE_ID) == conditions_before
