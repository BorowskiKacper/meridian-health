from app import config
from app.db.repositories import list_documents_by_patient, list_observations_by_patient, list_suggestions
from app.services.labs import extract_analytes, extract_lab_report

JANE_ID = "11111111-1111-4111-8111-111111111111"
IMAGE = b"fake-image-bytes"
MEDIA_TYPE = "image/jpeg"
ANALYTES = [
    {
        "name": "LDL",
        "value": 162,
        "unit": "mg/dL",
        "observed_at": "2026-09-01T00:00:00Z",
        "confidence": 0.9,
        "flag": "out_of_range",
    },
    {
        "name": "HDL",
        "value": 55,
        "unit": "mg/dL",
        "observed_at": "2026-09-01T00:00:00Z",
        "confidence": 0.4,
        "flag": "low_confidence",
    },
    {
        "name": "Glucose",
        "value": 90,
        "unit": "mg/dL",
        "observed_at": "2026-09-01T00:00:00Z",
        "confidence": 0.95,
        "flag": "ok",
    },
    {"name": "ALT", "value": 20, "unit": "U/L", "flag": "ok"},
]


class _Models:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.text, Exception):
            raise self.text
        return type("Response", (), {"text": self.text})()


class _Client:
    def __init__(self, api_key):
        self.models = _Client.models


def _contains(value, needle):
    if value == needle:
        return True
    if isinstance(value, (list, tuple)):
        return any(_contains(item, needle) for item in value)
    for attr in ("data", "mime_type"):
        if getattr(value, attr, None) == needle:
            return True
    inline = getattr(value, "inline_data", None)
    if inline is not None and _contains(inline, needle):
        return True
    return False


def test_extract_analytes_keeps_complete_rows(monkeypatch):
    import json

    _Client.models = _Models(json.dumps(ANALYTES))
    monkeypatch.setattr(config, "GEMINI_API_KEY", "gemini-key")
    monkeypatch.setattr("google.genai.Client", _Client)

    assert extract_analytes(IMAGE, MEDIA_TYPE) == ANALYTES[:3]
    call = _Client.models.calls[0]
    assert call["model"] == "gemini-3.6-flash"
    assert _contains(call["contents"], IMAGE)
    assert _contains(call["contents"], MEDIA_TYPE)


def test_extract_analytes_returns_empty_on_failure(monkeypatch):
    built = []

    def client(api_key):
        built.append(api_key)
        raise RuntimeError("down")

    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr("google.genai.Client", client)
    assert extract_analytes(IMAGE, MEDIA_TYPE) == []
    assert built == []

    monkeypatch.setattr(config, "GEMINI_API_KEY", "gemini-key")
    _Client.models = _Models(RuntimeError("down"))
    monkeypatch.setattr("google.genai.Client", _Client)
    assert extract_analytes(IMAGE, MEDIA_TYPE) == []


def test_vision_flags_become_suggestions_and_empty_vision_still_saves(
    seeded_db, monkeypatch
):
    import json

    session = seeded_db.session
    saved = {}
    monkeypatch.setattr(
        "app.services.labs.save_object",
        lambda storage_key, content: saved.__setitem__(storage_key, content),
    )
    _Client.models = _Models(json.dumps(ANALYTES))
    monkeypatch.setattr(config, "GEMINI_API_KEY", "gemini-key")
    monkeypatch.setattr("google.genai.Client", _Client)
    observations_before = list_observations_by_patient(session, JANE_ID)

    result = extract_lab_report(JANE_ID, IMAGE, MEDIA_TYPE, session=session)

    flags = {
        item["after"]["name"]: item["validation_flags"] for item in result["suggestions"]
    }
    assert flags["LDL"] == ["out_of_range"]
    assert flags["HDL"] == ["low_confidence"]
    assert flags["Glucose"] == []
    assert "ALT" not in flags
    assert list_observations_by_patient(session, JANE_ID) == observations_before
    assert saved

    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    before_docs = len(list_documents_by_patient(session, JANE_ID))
    before_suggestions = len(list_suggestions(session, JANE_ID))
    empty = extract_lab_report(JANE_ID, IMAGE, MEDIA_TYPE, session=session)
    assert empty["analytes"] == []
    assert empty["suggestions"] == []
    assert len(list_documents_by_patient(session, JANE_ID)) == before_docs + 1
    assert len(list_suggestions(session, JANE_ID)) == before_suggestions
