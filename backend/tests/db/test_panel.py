"""The clinic panel adds fictional charts without changing the demo patients."""

import importlib.util
from pathlib import Path

from app.db.repositories import (
    get_coverage_by_patient,
    list_appointments_by_patient,
    list_conditions_by_patient,
    list_encounters_by_patient,
    list_notes_by_patient,
    list_observations_by_patient,
    list_patients,
    list_reminders_by_patient,
)

JANE_ID = "11111111-1111-4111-8111-111111111111"
ROSA_ID = "44444444-4444-4444-8444-444444444441"

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _load(name):
    path = BACKEND_DIR / "seed" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"emr_{name}_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_panel_adds_eight_charts_and_skips_them_on_the_next_run(db, seed_fn):
    _load("demo").seed_demo(db, seed_fn)
    panel = _load("panel")

    assert panel.seed_panel(db) == 8
    assert panel.seed_panel(db) == 0
    assert len(list_patients(db)) == 11

    conditions = {row["name"] for row in list_conditions_by_patient(db, ROSA_ID)}
    assert "Heart failure with reduced ejection fraction" in conditions
    bnp = [row for row in list_observations_by_patient(db, ROSA_ID) if row["name"] == "NT-proBNP"]
    assert [row["value"] for row in sorted(bnp, key=lambda row: row["observed_at"])] == [
        1840.0,
        1210.0,
        860.0,
        720.0,
        640.0,
    ]
    assert any(len(row["body"]) > 200 for row in list_notes_by_patient(db, ROSA_ID))
    assert {row["name"] for row in list_reminders_by_patient(db, ROSA_ID)} == {
        "Blood pressure check",
        "Influenza vaccine",
    }

    for chart in panel.PANEL:
        patient_id = chart["id"]
        assert get_coverage_by_patient(db, patient_id)["member_id"] == chart["coverage"]["member_id"]
        assert list_encounters_by_patient(db, patient_id)
        assert list_observations_by_patient(db, patient_id)
        appointments = list_appointments_by_patient(db, patient_id)
        assert len(appointments) == 1
        assert appointments[0]["ends_at"] > appointments[0]["starts_at"]

    jane_a1c = [row for row in list_observations_by_patient(db, JANE_ID) if row["name"] == "A1c"]
    assert len(jane_a1c) == 8
