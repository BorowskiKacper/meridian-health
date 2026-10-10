from uuid import uuid4
from datetime import date

import pytest

from api_support import AMY_ID, JANE_ID, assert_error, bind_session
from app.db.models import Patient


@pytest.mark.parametrize("query", ["JANE", "doe jane", "1974-03-15", "R-111111", JANE_ID])
def test_patient_search_identity_matches(client, seeded_db, monkeypatch, query):
    bind_session(monkeypatch, seeded_db.session)
    response = client.get("/patients/search", params={"q": query})
    assert response.status_code == 200
    result = response.json()
    assert [row["id"] for row in result["patients"]] == [JANE_ID]
    assert set(result["patients"][0]) == {"id", "display_name", "date_of_birth", "sex"}
    assert result["has_more"] is False


def test_search_is_bounded_and_literal(client, seeded_db, monkeypatch):
    bind_session(monkeypatch, seeded_db.session)
    session = seeded_db.session
    for i in range(25):
        session.add(Patient(id=uuid4(), display_name=f"Test Directory {i:02}", date_of_birth=date(1980, 1, 1), sex="unknown", sms_opt_in=False, phone_e164=""))
    session.flush()
    result = client.get("/patients/search", params={"q": "test directory", "limit": 20}).json()
    assert len(result["patients"]) == 20
    assert result["has_more"] is True
    assert client.get("/patients/search", params={"q": "%_"}).json()["patients"] == []
    assert client.get("/patients/search", params={"q": "R-"}).json()["patients"] == []
    assert client.get("/patients/search", params={"q": "no matching name"}).json()["patients"] == []
    assert client.get("/patients/search", params={"limit": 1}).json()["patients"][0]["id"] == AMY_ID
    assert_error(client.get("/patients/search", params={"limit": 100}), 400, "validation_error")
