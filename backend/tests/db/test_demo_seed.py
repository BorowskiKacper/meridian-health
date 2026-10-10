"""The demo seed adds primary care depth without disturbing the base seed."""

import importlib.util
from pathlib import Path

from app.db.repositories import (
    get_body_region,
    list_allergies_by_patient,
    list_conditions_by_patient,
    list_encounters_by_patient,
    list_observations_by_patient,
    list_patients,
    list_reminders_by_patient,
    list_specialty_focus,
)
from app.services.chart import get_chart

JANE_ID = "11111111-1111-4111-8111-111111111111"
JOHN_ID = "22222222-2222-4222-8222-222222222222"
AMY_ID = "33333333-3333-4333-8333-333333333333"

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _load_demo():
    path = BACKEND_DIR / "seed" / "demo.py"
    spec = importlib.util.spec_from_file_location("emr_demo_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.seed_demo


def test_demo_seed_layers_on_the_base_seed(db, seed_fn):
    patient_ids = _load_demo()(db, seed_fn)

    assert set(patient_ids) == {JANE_ID, JOHN_ID, AMY_ID}
    assert len(list_patients(db)) == 3

    # Base rows survive.
    assert get_body_region(db, "heart")["mesh_name"] == "Heart"
    jane_conditions = {row["name"] for row in list_conditions_by_patient(db, JANE_ID)}
    assert {"Hypertension", "Type 2 diabetes", "Chronic kidney disease, stage 3a"} <= jane_conditions

    # Primary care focus covers every region.
    focus = {row["region_key"] for row in list_specialty_focus(db, "primary_care")}
    assert {"heart", "lung", "colon", "pancreas", "kidney", "liver", "thyroid", "breast", "cervix"} <= focus
    assert get_body_region(db, "pancreas")["mesh_name"] == "Pancreas"

    # Series long enough to draw a trend.
    a1c = [row for row in list_observations_by_patient(db, JANE_ID) if row["name"] == "A1c"]
    assert len(a1c) == 8
    assert len(list_encounters_by_patient(db, JANE_ID)) == 7

    # Jane keeps her allergies from the base seed.
    assert {row["substance"] for row in list_allergies_by_patient(db, JANE_ID)} == {"Penicillin", "Shellfish"}

    # Open care gaps are marked sent, so the SMS job does not resend them.
    gaps = {row["name"]: row["status"] for row in list_reminders_by_patient(db, JANE_ID)}
    assert gaps["A1c recheck"] == "sent"
    assert gaps["Colorectal cancer screening"] == "scheduled"


def test_chart_groups_series_from_the_demo_seed(db, seed_fn):
    _load_demo()(db, seed_fn)

    chart = get_chart(JANE_ID, session=db)

    a1c = next(series for series in chart["series"] if series["name"] == "A1c")
    assert a1c["unit"] == "%"
    assert a1c["body_region_key"] == "pancreas"
    assert [point["value"] for point in a1c["points"]] == [7.9, 7.4, 7.1, 7.3, 7.6, 7.8, 8.1, 8.4]
    assert a1c["points"][0]["at"] < a1c["points"][-1]["at"]
    pancreas = next(region for region in chart["regions"] if region["region_key"] == "pancreas")
    assert "primary_care" in pancreas["specialties"]
    assert "endocrinology" in pancreas["specialties"]
