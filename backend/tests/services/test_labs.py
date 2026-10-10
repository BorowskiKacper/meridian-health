import copy
import uuid
from pathlib import Path

from app.db.repositories import (
    get_suggestion,
    list_documents_by_patient,
    list_observations_by_patient,
    list_suggestions,
)
from app.schemas import Suggestion
from app.services.labs import extract_lab_report

JANE_ID = "11111111-1111-4111-8111-111111111111"
IMAGE = b"fake-image-bytes"
MEDIA_TYPE = "image/jpeg"
LABS_SOURCE = Path(__file__).resolve().parents[2] / "app" / "services" / "labs.py"

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
]

VALIDATION_FLAGS = {
    "LDL": ["out_of_range"],
    "HDL": ["low_confidence"],
    "Glucose": [],
}


def invoke(fn, *args, session, **kwargs):
    import inspect

    if "session" in inspect.signature(fn).parameters:
        kwargs["session"] = session
    return fn(*args, **kwargs)


def install_seams(monkeypatch, tmp_path):
    analyte_calls = []
    propose_calls = []

    def extract_analytes(content, media_type):
        analyte_calls.append((content, media_type))
        return copy.deepcopy(ANALYTES)

    def storage_root():
        return tmp_path

    def propose_change(*args, **kwargs):
        propose_calls.append((args, kwargs))
        raise AssertionError("propose_change was called")

    monkeypatch.setattr(
        "app.services.labs.extract_analytes",
        extract_analytes,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.labs.storage_root",
        storage_root,
        raising=False,
    )
    monkeypatch.setattr(
        "app.mcp.tools.propose_change",
        propose_change,
        raising=False,
    )
    return analyte_calls, propose_calls, storage_root


def rows_by_id(rows):
    return {row["id"]: row for row in rows}


def assert_uuid_string(value):
    assert isinstance(value, str)
    assert str(uuid.UUID(value)) == value


def assert_response_suggestion(item, stored):
    assert isinstance(item, dict)
    assert item["id"] == stored["id"]
    body = dict(item)
    if "unconfirmed" not in stored:
        assert body.get("unconfirmed", False) is False
        body.pop("unconfirmed", None)
    assert body == stored


def assert_stored_suggestion(stored, analyte):
    assert stored["kind"] == "observation"
    assert stored["target_table"] == "observations"
    assert stored["source"] == "lab_report"
    assert stored["status"] == "pending"
    assert stored["patient_id"] == JANE_ID
    after = stored["after"]
    assert after["name"] == analyte["name"]
    assert after["value"] == analyte["value"]
    assert after["unit"] == analyte["unit"]
    assert after["observed_at"] == analyte["observed_at"]
    assert stored["confidence"] == analyte["confidence"]
    assert stored["validation_flags"] == VALIDATION_FLAGS[analyte["name"]]
    payload = dict(stored)
    if "unconfirmed" not in payload:
        payload["unconfirmed"] = False
    Suggestion.model_validate(payload)


def test_extract_lab_report_saves_photo_and_inserts_suggestions(
    seeded_db, tmp_path, monkeypatch
):
    session = seeded_db.session
    analyte_calls, propose_calls, storage_root = install_seams(monkeypatch, tmp_path)
    observations_before = list_observations_by_patient(session, JANE_ID)
    suggestions_before = list_suggestions(session, JANE_ID)

    result = invoke(
        extract_lab_report,
        JANE_ID,
        IMAGE,
        MEDIA_TYPE,
        session=session,
    )

    assert isinstance(result, dict)
    assert set(result) == {"document_id", "analytes", "suggestions"}
    assert result["analytes"] == ANALYTES
    assert_uuid_string(result["document_id"])
    assert analyte_calls == [(IMAGE, MEDIA_TYPE)]
    assert propose_calls == []

    documents = list_documents_by_patient(session, JANE_ID)
    assert len(documents) == 1
    document = documents[0]
    assert document["id"] == result["document_id"]
    assert document["patient_id"] == JANE_ID
    assert document["media_type"] == MEDIA_TYPE
    storage_key = document["storage_key"]
    assert isinstance(storage_key, str) and storage_key
    assert not Path(storage_key).is_absolute()
    assert str(tmp_path) not in storage_key
    saved = Path(storage_root()) / storage_key
    assert saved.is_file()
    assert saved.read_bytes() == IMAGE

    observations = list_observations_by_patient(session, JANE_ID)
    assert rows_by_id(observations) == rows_by_id(observations_before)

    suggestions = list_suggestions(session, JANE_ID)
    before_ids = {row["id"] for row in suggestions_before}
    new_rows = [row for row in suggestions if row["id"] not in before_ids]
    assert len(new_rows) == 3
    pending_ids = {
        row["id"] for row in list_suggestions(session, JANE_ID, "pending")
    }
    assert {row["id"] for row in new_rows} <= pending_ids

    by_name = {}
    for row in new_rows:
        fetched = get_suggestion(session, row["id"])
        assert fetched == row
        name = fetched["after"]["name"]
        assert name not in by_name
        by_name[name] = fetched
    assert set(by_name) == {analyte["name"] for analyte in ANALYTES}
    for analyte in ANALYTES:
        assert_stored_suggestion(by_name[analyte["name"]], analyte)

    response_suggestions = result["suggestions"]
    assert isinstance(response_suggestions, list)
    assert len(response_suggestions) == len(new_rows)
    response_by_id = {}
    for item in response_suggestions:
        assert item["id"] not in response_by_id
        response_by_id[item["id"]] = item
    assert set(response_by_id) == {row["id"] for row in new_rows}
    for row in new_rows:
        assert_response_suggestion(response_by_id[row["id"]], row)


def test_labs_source_does_not_reference_mcp():
    source = LABS_SOURCE.read_text(encoding="utf-8")
    assert "app.mcp" not in source
    assert "propose_change" not in source
