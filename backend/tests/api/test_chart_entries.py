from uuid import UUID, uuid4
from datetime import timezone

import pytest
from sqlalchemy import select

from api_support import AMY_ID, JANE_ID, JOHN_ID, UNKNOWN_ID, assert_error, bind_session
from app.db.models import AuditLog, Observation, Reminder


def submission(**fields):
    return {"submission_id": str(uuid4()), **fields}


def test_vitals_persist_and_retry_does_not_duplicate(client, seeded_db, monkeypatch):
    session = seeded_db.session
    bind_session(monkeypatch, session)
    data = submission(observed_at="2025-10-10T10:15:00-04:00", systolic=120, diastolic=76, weight_kg=66.2, pulse=74)
    path = f"/patients/{AMY_ID}/vitals"
    assert client.post(path, json=data).status_code == 200
    session.commit()
    session.expire_all()
    assert client.post(path, json=data).status_code == 200
    rows = session.scalars(select(Observation).where(Observation.patient_id == UUID(AMY_ID), Observation.source == "manual_entry")).all()
    assert len(rows) == 4
    assert all(r.observed_at.astimezone(timezone.utc).isoformat() == "2025-10-10T14:15:00+00:00" for r in rows)
    chart = client.get(f"/patients/{AMY_ID}/chart").json()
    weight = next(s for s in chart["series"] if s["name"] == "Body weight")
    assert any(p["value"] == 66.2 and p["source"] == "manual_entry" for p in weight["points"])
    assert_error(client.post(path, json={**data, "weight_kg": 67}), 409, "invalid_state")
    assert_error(client.post(f"/patients/{JANE_ID}/vitals", json=data), 409, "invalid_state")


@pytest.mark.parametrize("values", [{}, {"systolic": 120}, {"weight_kg": -1}, {"pulse": "NaN"}, {"pulse": 70, "observed_at": "2099-01-01T00:00:00Z"}, {"pulse": 70, "observed_at": "2025-01-01T00:00:00"}])
def test_invalid_vitals_do_not_write(client, seeded_db, monkeypatch, values):
    bind_session(monkeypatch, seeded_db.session)
    data = submission(observed_at="2025-01-01T00:00:00Z", **{k: v for k, v in values.items() if k != "observed_at"})
    if "observed_at" in values:
        data["observed_at"] = values["observed_at"]
    assert_error(client.post(f"/patients/{AMY_ID}/vitals", json=data), 400, "validation_error")
    assert seeded_db.session.get(AuditLog, UUID(data["submission_id"])) is None


def test_unknown_patient_and_invalid_region(client, seeded_db, monkeypatch):
    bind_session(monkeypatch, seeded_db.session)
    assert_error(client.post(f"/patients/{UNKNOWN_ID}/vitals", json=submission(observed_at="2025-01-01T00:00:00Z", pulse=70)), 404, "not_found")
    assert_error(client.post(f"/patients/{AMY_ID}/problems", json=submission(name="Test problem", status="active", onset_date="2025-01-01", body_region_key="invented")), 400, "validation_error")


def test_medication_review_and_cross_patient_edit(client, seeded_db, monkeypatch):
    session = seeded_db.session
    bind_session(monkeypatch, session)
    medication = submission(name="Demo medication", dose="10 mg", route="oral", frequency="daily", status="active", start_date="2025-01-01", body_region_key="heart")
    assert client.post(f"/patients/{AMY_ID}/medications", json=medication).status_code == 200
    session.commit()
    chart = client.get(f"/patients/{AMY_ID}/chart").json()
    records = chart["medications"]
    state = client.get(f"/patients/{AMY_ID}/entry-state").json()
    review = submission(kind="medications", record_ids=[r["id"] for r in records], medication_use={r["id"]: "taking" for r in records}, note="Reviewed with patient", confirmed_with_patient=True, expected_version=state["versions"]["medications"])
    assert client.post(f"/patients/{AMY_ID}/chart-review", json=review).status_code == 200
    session.commit()
    assert not client.get(f"/patients/{AMY_ID}/entry-state").json()["medications"]["stale"]
    record_id = next(r["id"] for r in records if r["name"] == "Demo medication")
    changed = {**medication, "submission_id": str(uuid4()), "status": "stopped"}
    assert_error(client.put(f"/patients/{JANE_ID}/medications/{record_id}", json=changed), 404, "not_found")
    assert client.put(f"/patients/{AMY_ID}/medications/{record_id}", json=changed).status_code == 200
    assert client.get(f"/patients/{AMY_ID}/entry-state").json()["medications"]["stale"]
    assert_error(client.post(f"/patients/{AMY_ID}/chart-review", json={**review, "submission_id": str(uuid4())}), 409, "invalid_state")


def test_visit_draft_survives_reload_without_signed_note(client, seeded_db, monkeypatch):
    session = seeded_db.session
    bind_session(monkeypatch, session)
    notes_before = client.get(f"/patients/{AMY_ID}/chart").json()["notes"]
    draft = submission(visit_date="2025-10-10", reason="Demo follow-up", assessment="Review results", plan="Discuss at visit")
    assert client.post(f"/patients/{AMY_ID}/visit-draft", json=draft).status_code == 200
    session.commit()
    session.expire_all()
    assert client.get(f"/patients/{AMY_ID}/entry-state").json()["draft"]["reason"] == draft["reason"]
    assert client.get(f"/patients/{JANE_ID}/entry-state").json()["draft"] is None
    assert client.get(f"/patients/{AMY_ID}/chart").json()["notes"] == notes_before


def test_allergy_conflict_requires_resolving_nkda(client, seeded_db, monkeypatch):
    session = seeded_db.session
    bind_session(monkeypatch, session)
    chart = client.get(f"/patients/{JOHN_ID}/chart").json()
    nkda = next(r for r in chart["patient"]["allergies"] if r["category"] == "nkda")
    allergy = submission(substance="Demo drug", category="drug", reaction="Hives", severity="moderate", status="active", recorded_on="2025-10-10")
    assert_error(client.post(f"/patients/{JOHN_ID}/allergies", json=allergy), 409, "invalid_state")
    assert_error(client.put(f"/patients/{AMY_ID}/allergies/{nkda['id']}/status", json=submission(status="inactive")), 404, "not_found")
    assert client.put(f"/patients/{JOHN_ID}/allergies/{nkda['id']}/status", json=submission(status="inactive")).status_code == 200
    assert client.post(f"/patients/{JOHN_ID}/allergies", json=allergy).status_code == 200
    session.commit()
    allergies = client.get(f"/patients/{JOHN_ID}/chart").json()["patient"]["allergies"]
    assert any(r["substance"] == "Demo drug" and r["status"] == "active" for r in allergies)
    assert any(r["category"] == "nkda" and r["status"] == "inactive" for r in allergies)


def test_follow_up_update_is_patient_bound_and_persisted(client, seeded_db, monkeypatch):
    session = seeded_db.session
    bind_session(monkeypatch, session)
    row = session.scalar(select(Reminder).where(Reminder.patient_id == UUID(AMY_ID)))
    data = submission(due_on="2026-11-01", status="done")
    assert_error(client.put(f"/patients/{JANE_ID}/follow-up/{row.id}", json=data), 404, "not_found")
    assert client.put(f"/patients/{AMY_ID}/follow-up/{row.id}", json=data).status_code == 200
    session.commit()
    session.expire_all()
    saved = next(r for r in client.get(f"/patients/{AMY_ID}/chart").json()["reminders"] if r["id"] == str(row.id))
    assert saved["status"] == "done"
    assert saved["due_on"] == "2026-11-01"


def test_overlong_draft_is_rejected_without_receipt(client, seeded_db, monkeypatch):
    bind_session(monkeypatch, seeded_db.session)
    data = submission(visit_date="2025-10-10", reason="Test", assessment="x" * 7000, plan="")
    assert_error(client.post(f"/patients/{AMY_ID}/visit-draft", json=data), 400, "validation_error")
    assert seeded_db.session.get(AuditLog, UUID(data["submission_id"])) is None


def test_explicit_nkda_requires_confirmation_and_no_active_drug_allergy(client, seeded_db, monkeypatch):
    bind_session(monkeypatch, seeded_db.session)
    data = submission(recorded_on="2025-10-10", confirmed_with_patient=True)
    assert_error(client.post(f"/patients/{JANE_ID}/no-known-drug-allergies", json=data), 409, "invalid_state")
    chart = client.get(f"/patients/{JOHN_ID}/chart").json()
    nkda = next(r for r in chart["patient"]["allergies"] if r["category"] == "nkda")
    assert client.put(f"/patients/{JOHN_ID}/allergies/{nkda['id']}/status", json=submission(status="inactive")).status_code == 200
    assert_error(client.post(f"/patients/{JOHN_ID}/no-known-drug-allergies", json={**data, "confirmed_with_patient": False}), 400, "validation_error")
    assert client.post(f"/patients/{JOHN_ID}/no-known-drug-allergies", json=data).status_code == 200
    assert client.post(f"/patients/{JOHN_ID}/no-known-drug-allergies", json=data).status_code == 200
