import copy
import sys
import types
import uuid
from datetime import date

import app.evidence as evidence
import app.mcp.tools as mcp_tools
from app.db.repositories import (
    get_request,
    insert_suggestion,
    list_conditions_by_patient,
    list_notes_by_patient,
    list_reminders_by_patient,
    list_suggestions,
)

JANE_ID = "11111111-1111-4111-8111-111111111111"
MEMBER_ID = "NW-1001"
PHONE = "+15555550101"
SCREENING_DUE = "2026-10-01"
SCREENING_DUE_DATE = date(2026, 10, 1)
IDENTIFIERS = (JANE_ID, MEMBER_ID, PHONE, SCREENING_DUE)
LEAKED_TEXT = (
    f"colorectal cancer screening start age {JANE_ID} {MEMBER_ID} {PHONE} {SCREENING_DUE}"
)
DEPARTURE_REASON = (
    "USPSTF baseline: start at 45 for average risk. "
    "Proposed 40 because a first-degree relative was diagnosed with colorectal cancer."
)
RESPONSE_KEYS = {
    "request_id",
    "transcript",
    "route",
    "suggestions",
    "answer",
    "spoken_text",
    "audio_base64",
}


def invoke(fn, *args, session, **kwargs):
    import inspect

    if "session" in inspect.signature(fn).parameters:
        kwargs["session"] = session
    return fn(*args, **kwargs)


def baseline_citation():
    return {
        "source_id": "uspstf:colorectal-cancer-screening#2",
        "title": "USPSTF Colorectal Cancer: Screening: Clinician Summary",
        "passage": (
            "For adults aged 45 to 49 years: Screen adults aged 45 to 49 years "
            "for colorectal cancer. Grade B"
        ),
        "locator": (
            "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/"
            "colorectal-cancer-screening"
        ),
        "tier": "baseline",
    }


def guideline_citation():
    return {
        "source_id": "acg:colorectal-cancer-screening",
        "title": "ACG colorectal cancer screening guideline",
        "passage": (
            "Patients with a first-degree relative diagnosed with colorectal cancer "
            "should begin screening earlier than average risk."
        ),
        "locator": "https://gi.org/guideline/colorectal-cancer-screening",
        "tier": "guideline",
    }


def literature_citation():
    return {
        "source_id": "pubmed:colorectal-family-history",
        "title": "Family history and earlier colorectal cancer screening",
        "passage": (
            "A first-degree relative diagnosed with colorectal cancer before age 60 "
            "supports starting screening before the average-risk age."
        ),
        "locator": "https://pubmed.ncbi.nlm.nih.gov/00000000/",
        "tier": "literature",
    }


def chart_citation(note):
    locator = f"note:{note['id']}"
    return {
        "source_id": locator,
        "title": "Chart note",
        "passage": note["body"],
        "locator": locator,
        "tier": "chart",
    }


def field_update(citations, target_id):
    return {
        "patient_id": JANE_ID,
        "request_id": None,
        "kind": "field_update",
        "status": "pending",
        "target_table": "conditions",
        "target_id": target_id,
        "before": {"status": "active"},
        "after": {"status": "controlled"},
        "reason": "Recent readings show hypertension is controlled.",
        "confidence": 0.9,
        "citations": citations,
        "validation_flags": [],
        "source": "chart_agent",
    }


def reminder_change(citations, reason=DEPARTURE_REASON):
    return {
        "patient_id": JANE_ID,
        "request_id": None,
        "kind": "reminder_change",
        "status": "pending",
        "target_table": "reminder_schedule",
        "target_id": None,
        "before": {"due_on": SCREENING_DUE, "status": "scheduled"},
        "after": {"due_on": "2026-12-01", "status": "scheduled"},
        "reason": reason,
        "confidence": 0.9,
        "citations": citations,
        "validation_flags": [],
        "source": "reminder_agent",
    }


def evidence_tool_calls(*, include_notes=False):
    calls = [
        {"name": "search_guidelines", "text": LEAKED_TEXT, "corpus": "uspstf"},
        {"name": "search_guidelines", "text": LEAKED_TEXT, "corpus": "pubmed"},
        {"name": "search_medical_web", "text": LEAKED_TEXT},
    ]
    if include_notes:
        calls.append({"name": "search_patient_notes", "query": "LDL"})
    return calls


def support_all(payload):
    return {
        "supported": [
            {
                "sentence": payload["text"],
                "citation_indexes": list(range(len(payload["citations"]))),
            }
        ],
        "removed": [],
    }


class DoctorModel:
    def __init__(self, *, route=None, chart=None, research=None, reminders=None, verify=None):
        self.calls = []
        self.route = route
        self.chart = chart
        self.research = research
        self.reminders = reminders
        self.verify = support_all if verify is None else verify
        self._counts = {"research": 0, "reminders": 0}

    def __call__(self, task, payload):
        try:
            recorded = copy.deepcopy(payload)
        except Exception:
            recorded = payload
        self.calls.append((task, recorded))
        if task == "classify":
            return {"route": self.route}
        if task == "chart":
            return copy.deepcopy(self.chart)
        if task == "research":
            return self._once("research", self.research)
        if task == "reminders":
            return self._once("reminders", self.reminders)
        if task == "verify":
            if callable(self.verify):
                return self.verify(payload)
            return copy.deepcopy(self.verify)
        raise AssertionError(task)

    def _once(self, task, body):
        self._counts[task] += 1
        response = copy.deepcopy(body)
        if self._counts[task] > 1:
            response["tool_calls"] = []
        return response


class Harness:
    def __init__(self, model):
        self.model = model
        self.evidence_calls = []
        self.propose_calls = []
        self.context_calls = []


def install(monkeypatch, model):
    harness = Harness(model)
    _install_model(monkeypatch, model)
    _install_evidence(monkeypatch, harness.evidence_calls)
    _install_mcp(monkeypatch, harness)
    return harness


def _install_model(monkeypatch, fake):
    import app.agents.doctor as doctor_pkg

    name = "app.agents.doctor.model"
    try:
        __import__(name)
    except ModuleNotFoundError:
        module = types.ModuleType(name)
        module.__package__ = "app.agents.doctor"
        module.complete = fake
        monkeypatch.setitem(sys.modules, name, module)
        monkeypatch.setattr(doctor_pkg, "model", module, raising=False)
    monkeypatch.setattr("app.agents.doctor.model.complete", fake, raising=False)


def _install_evidence(monkeypatch, calls):
    def search_guidelines(text, corpus):
        calls.append(("search_guidelines", text, corpus))
        return {"passages": []}

    def search_medical_web(text):
        calls.append(("search_medical_web", text))
        return {"passages": []}

    def web_search(*_args, **_kwargs):
        raise AssertionError("web_search")

    monkeypatch.setattr(evidence, "search_guidelines", search_guidelines)
    monkeypatch.setattr(evidence, "search_medical_web", search_medical_web)
    monkeypatch.setattr(evidence, "web_search", web_search)


def _install_mcp(monkeypatch, harness):
    real_propose = mcp_tools.propose_change
    real_context = mcp_tools.get_patient_context

    def propose_change(*args, **kwargs):
        harness.propose_calls.append((args, kwargs))
        return real_propose(*args, **kwargs)

    def get_patient_context(*args, **kwargs):
        harness.context_calls.append((args, kwargs))
        return real_context(*args, **kwargs)

    monkeypatch.setattr(mcp_tools, "propose_change", propose_change)
    monkeypatch.setattr(mcp_tools, "get_patient_context", get_patient_context)


def payloads(model, task):
    return [payload for name, payload in model.calls if name == task]


def jane_hypertension(session):
    rows = [
        row
        for row in list_conditions_by_patient(session, JANE_ID)
        if row["name"] == "Hypertension"
    ]
    assert len(rows) == 1
    assert rows[0]["status"] == "active"
    return rows[0]


def jane_note(session):
    notes = list_notes_by_patient(session, JANE_ID)
    assert notes
    return notes[0]


def jane_screening(session):
    rows = [
        row
        for row in list_reminders_by_patient(session, JANE_ID)
        if row["name"] == "Colorectal cancer screening"
    ]
    assert len(rows) == 1
    assert rows[0]["status"] == "scheduled"
    assert rows[0]["due_on"] == SCREENING_DUE_DATE
    return rows[0]


def condition_status(session):
    return {
        row["id"]: row["status"] for row in list_conditions_by_patient(session, JANE_ID)
    }


def reminder_snapshot(session):
    return [
        (row["id"], row["due_on"], row["status"])
        for row in list_reminders_by_patient(session, JANE_ID)
    ]


def pending_ids(session):
    return {row["id"] for row in list_suggestions(session, JANE_ID, "pending")}


def insert_pending_chart_suggestion(session):
    row = {
        "id": str(uuid.uuid4()),
        "patient_id": JANE_ID,
        "request_id": None,
        "kind": "field_update",
        "status": "pending",
        "target_table": "conditions",
        "target_id": None,
        "before": {"status": "active"},
        "after": {"status": "controlled"},
        "reason": "Unconfirmed chart suggestion.",
        "confidence": 0.9,
        "citations": [],
        "validation_flags": [],
        "source": "chart_agent",
    }
    saved = insert_suggestion(session, row)
    assert saved["status"] == "pending"
    assert saved["id"] in pending_ids(session)
    return saved


def find_unconfirmed(value, suggestion_id):
    if isinstance(value, dict):
        if str(value.get("id", "")) == str(suggestion_id) and value.get("unconfirmed") is True:
            return value
        for child in value.values():
            found = find_unconfirmed(child, suggestion_id)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_unconfirmed(child, suggestion_id)
            if found is not None:
                return found
    return None


def assert_request(session, result, *, text, channel, route):
    assert isinstance(result, dict)
    assert set(result) == RESPONSE_KEYS
    assert isinstance(result["request_id"], str)
    uuid.UUID(result["request_id"])
    assert result["transcript"] == text
    assert result["route"] == route
    stored = get_request(session, result["request_id"])
    assert isinstance(stored, dict)
    assert stored["id"] == result["request_id"]
    assert str(stored["patient_id"]) == JANE_ID
    assert stored["channel"] == channel
    assert stored["role"] == "doctor"
    assert stored["transcript"] == text
    assert stored["route"] == route


def assert_typed_silent(result):
    assert result["spoken_text"] is None
    assert result["audio_base64"] is None


def assert_context_call(harness):
    assert harness.context_calls
    saw_jane = False
    for args, kwargs in harness.context_calls:
        patient_id = kwargs.get("patient_id", args[0] if args else None)
        if str(patient_id) == JANE_ID:
            saw_jane = True
    assert saw_jane


def assert_proposed(harness, kind):
    assert harness.propose_calls
    for args, kwargs in harness.propose_calls:
        patient_id = kwargs.get("patient_id", args[0] if args else None)
        suggestion = kwargs.get("suggestion", args[1] if len(args) > 1 else None)
        assert str(patient_id) == JANE_ID
        assert isinstance(suggestion, dict)
        assert suggestion["kind"] == kind


def assert_new_pending(session, before_ids, suggestions):
    assert isinstance(suggestions, list)
    assert suggestions
    after_ids = pending_ids(session)
    returned_ids = set()
    for item in suggestions:
        assert isinstance(item, dict)
        assert item["status"] == "pending"
        assert item["id"] in after_ids
        returned_ids.add(item["id"])
    assert returned_ids == after_ids - before_ids
    assert before_ids.isdisjoint(returned_ids)


def assert_rules(payload):
    assert payload["trigger"] in {"doctor_request", "post_approval"}
    assert isinstance(payload["context"], dict)
    assert "rules" in payload
    rules = payload["rules"]
    assert rules not in (None, [], {})
    rendered = str(rules).lower()
    assert "45" in rendered or "colorectal" in rendered


def assert_deidentified_evidence(calls):
    assert calls
    corpora = set()
    saw_medical_web = False
    for call in calls:
        assert call[0] in {"search_guidelines", "search_medical_web"}
        text = call[1]
        assert isinstance(text, str)
        for token in IDENTIFIERS:
            assert token not in text
        if call[0] == "search_guidelines":
            assert call[2] in {"uspstf", "pubmed"}
            corpora.add(call[2])
        else:
            saw_medical_web = True
    assert corpora == {"uspstf", "pubmed"}
    assert saw_medical_web


def assert_model_leaked_tool_text(payload):
    asked = [
        call["text"]
        for call in payload["tool_calls"]
        if call["name"] in {"search_guidelines", "search_medical_web"}
    ]
    assert asked
    assert all(JANE_ID in text for text in asked)
    assert {call["corpus"] for call in payload["tool_calls"] if call["name"] == "search_guidelines"} == {
        "uspstf",
        "pubmed",
    }


def assert_departure_reason(reason):
    assert isinstance(reason, str)
    assert "45" in reason
    assert "40" in reason
    assert "baseline" in reason.lower()


def citation_tiers(citations):
    return {item["tier"] for item in citations}
