from app.bootstrap import _load
from app.db.repositories import list_observations_by_patient


def test_vitals_are_labeled_idempotent_and_preserve_original_records(db, seed_fn):
    patient_ids = seed_fn(db)
    original = {patient_id: list_observations_by_patient(db, patient_id) for patient_id in patient_ids}
    seed_vitals = _load("vitals").seed_vitals
    added = seed_vitals(db)
    assert added > 0
    assert seed_vitals(db) == 0
    total_added = 0
    for patient_id in patient_ids:
        rows = list_observations_by_patient(db, patient_id)
        by_id = {row["id"]: row for row in rows}
        for row in original[patient_id]:
            assert by_id[row["id"]] == row
        synthetic = [row for row in rows if row["source"] == "demo_vitals"]
        total_added += len(synthetic)
        assert any(row["name"] == "Body weight" for row in synthetic)
        assert all(row["observed_at"].year <= 2025 for row in synthetic)
    assert total_added == added


def test_vitals_do_not_create_patients_in_an_empty_clinic(db):
    assert _load("vitals").seed_vitals(db) == 0
