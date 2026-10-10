from app.db.repositories import list_observations_by_patient
from api_support import JANE_ID, bind_session, call

LDL = {
    "name": "LDL",
    "value": 162,
    "unit": "mg/dL",
    "observed_at": "2026-09-01T00:00:00Z",
    "confidence": 0.9,
    "flag": "out_of_range",
}


def test_lab_photo_returns_a_pending_observation(seeded_db, monkeypatch, client, tmp_path):
    bind_session(monkeypatch, seeded_db.session)
    session = seeded_db.session

    def extract_analytes(content, media_type):
        return [dict(LDL)]

    monkeypatch.setattr("app.services.labs.extract_analytes", extract_analytes)
    monkeypatch.setattr("app.services.labs.storage_root", lambda: tmp_path)
    monkeypatch.setattr(
        "app.api.routes.documents.extract_analytes",
        extract_analytes,
        raising=False,
    )
    before = list_observations_by_patient(session, JANE_ID)

    response = call(
        client,
        "POST",
        "/documents",
        data={"patient_id": JANE_ID},
        files={"file": ("labs.jpg", b"lab-photo", "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"]
    assert body["analytes"] == [LDL]
    assert len(body["suggestions"]) == 1
    suggestion = body["suggestions"][0]
    assert suggestion["status"] == "pending"
    assert suggestion["kind"] == "observation"
    assert list_observations_by_patient(session, JANE_ID) == before
