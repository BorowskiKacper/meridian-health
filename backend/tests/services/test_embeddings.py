from uuid import uuid4

from app import config
from app.db.repositories import insert_suggestion, list_notes_by_patient
from app.services.approval import approve_suggestions, embed_text

JANE_ID = "11111111-1111-4111-8111-111111111111"
SOAP_BODY = "Hypertension is controlled."


class _Embedding:
    def __init__(self, values):
        self.values = values


class _EmbedResult:
    def __init__(self, values):
        self.embeddings = [_Embedding(values)]


class _Models:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def embed_content(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class _Client:
    def __init__(self, api_key):
        self.models = _Client.models


def _suggestion(session):
    return insert_suggestion(
        session,
        {
            "id": str(uuid4()),
            "patient_id": JANE_ID,
            "request_id": None,
            "kind": "soap_note",
            "status": "pending",
            "target_table": "notes",
            "target_id": None,
            "before": {},
            "after": {"body": SOAP_BODY},
            "reason": "Note from the visit.",
            "confidence": 0.9,
            "citations": [],
            "validation_flags": [],
            "source": "chart_agent",
        },
    )


def test_embed_text_returns_768_floats(monkeypatch):
    values = [0.25] * 768
    _Client.models = _Models(_EmbedResult(values))
    monkeypatch.setattr(config, "GEMINI_API_KEY", "gemini-key")
    monkeypatch.setattr("google.genai.Client", _Client)

    assert embed_text("hello") == values
    call = _Client.models.calls[0]
    assert call["model"] == "gemini-embedding-001"
    assert call["contents"] == "hello"
    assert call["config"].output_dimensionality == 768


def test_embed_text_returns_none_without_a_zero_vector(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(
        "google.genai.Client",
        lambda api_key: (_ for _ in ()).throw(AssertionError("client built")),
    )

    assert embed_text("hello") is None

    monkeypatch.setattr(config, "GEMINI_API_KEY", "gemini-key")
    _Client.models = _Models(RuntimeError("down"))
    monkeypatch.setattr("google.genai.Client", _Client)
    assert embed_text("hello") is None

    _Client.models = _Models(_EmbedResult([0.1, 0.2]))
    assert embed_text("hello") is None


def test_failed_embedding_still_stores_the_note(seeded_db, monkeypatch):
    session = seeded_db.session
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(
        "app.agents.doctor.run_reminder_agent",
        lambda patient_id, trigger, session=None: {
            "suggestions": [],
            "answer": "Screenings are up to date.",
        },
    )
    suggestion = _suggestion(session)
    before = {note["id"] for note in list_notes_by_patient(session, JANE_ID)}

    result = approve_suggestions([suggestion["id"]], None, session=session)

    assert suggestion["id"] in {row["id"] for row in result["approved"]}
    notes = [
        note
        for note in list_notes_by_patient(session, JANE_ID)
        if note["id"] not in before
    ]
    assert len(notes) == 1
    assert notes[0]["body"] == SOAP_BODY
    assert notes[0]["embedding"] is None
