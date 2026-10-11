"""Primary care depth on top of the base seed, for the running clinic.

The base seed in ``seed.py`` is the contract the tests pin. This module keeps
those rows and adds what a primary care workspace needs to show trends and
care gaps: more body regions, a primary_care focus, a problem list per
patient, observation series, office visits and screening reminders.
"""

from datetime import date, datetime, timezone
from uuid import uuid4

from app.db.repositories import (
    get_body_region,
    insert_body_region,
    insert_condition,
    insert_encounter,
    insert_family_history,
    insert_medication,
    insert_note,
    insert_observation,
    insert_reminder,
    insert_reminder_rule,
    insert_specialty_focus,
    list_all_specialty_focus,
    list_reminder_rules,
)

JANE_ID = "11111111-1111-4111-8111-111111111111"
JOHN_ID = "22222222-2222-4222-8222-222222222222"
AMY_ID = "33333333-3333-4333-8333-333333333333"

_UTC = timezone.utc

EXTRA_REGIONS = (
    ("pancreas", "Pancreas", "Pancreas"),
    ("kidney", "Kidneys", "Kidney"),
    ("liver", "Liver", "Liver"),
    ("thyroid", "Thyroid", "Thyroid"),
    ("breast", "Breast", "Breast"),
    ("cervix", "Cervix", "Cervix"),
)

EXTRA_FOCUS = (
    ("cardiology", "kidney"),
    ("gastroenterology", "liver"),
    ("endocrinology", "pancreas"),
    ("endocrinology", "thyroid"),
    ("nephrology", "kidney"),
    ("primary_care", "heart"),
    ("primary_care", "lung"),
    ("primary_care", "colon"),
    ("primary_care", "pancreas"),
    ("primary_care", "kidney"),
    ("primary_care", "liver"),
    ("primary_care", "thyroid"),
    ("primary_care", "breast"),
    ("primary_care", "cervix"),
)

EXTRA_RULES = (
    ("Mammography", 40, "uspstf:breast-cancer-screening"),
    ("Cervical cancer screening", 21, "uspstf:cervical-cancer-screening"),
    ("A1c recheck", 35, "ada:standards-of-care-glycemic-targets"),
    ("Diabetic eye exam", 35, "ada:standards-of-care-retinopathy"),
    ("Blood pressure check", 18, "uspstf:hypertension-screening"),
    ("Influenza vaccine", 18, "cdc:acip-influenza"),
)


def _id():
    return str(uuid4())


def _at(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=_UTC)


def seed_demo(session, base_seed):
    """Run ``base_seed`` (the ``seed`` function from seed.py) then add depth."""
    patient_ids = base_seed(session)
    ensure_reference(session)
    rules = {row["name"]: row["id"] for row in list_reminder_rules(session)}
    _jane(session, rules)
    _john(session, rules)
    _amy(session, rules)
    return patient_ids


def ensure_reference(session):
    """Insert regions, focus rows, and reminder rules, skipping any already stored.

    A database that already has the original patients never re-runs the demo
    seed. Panel charts still reference these keys, so bootstrap calls this
    before inserting them.
    """
    for region_key, display_name, mesh_name in EXTRA_REGIONS:
        if get_body_region(session, region_key) is not None:
            continue
        insert_body_region(
            session,
            {"region_key": region_key, "display_name": display_name, "mesh_name": mesh_name},
        )
    present_focus = {
        (row["specialty_key"], row["region_key"]) for row in list_all_specialty_focus(session)
    }
    for specialty_key, region_key in EXTRA_FOCUS:
        if (specialty_key, region_key) in present_focus:
            continue
        insert_specialty_focus(
            session, {"specialty_key": specialty_key, "region_key": region_key}
        )
    present_rules = {row["name"] for row in list_reminder_rules(session)}
    for name, baseline_age, source in EXTRA_RULES:
        if name in present_rules:
            continue
        insert_reminder_rule(
            session,
            {
                "id": _id(),
                "name": name,
                "baseline_age": baseline_age,
                "guideline_source_id": source,
            },
        )


def _condition(session, patient_id, name, status, onset, region):
    insert_condition(
        session,
        {
            "id": _id(),
            "patient_id": patient_id,
            "name": name,
            "status": status,
            "onset_date": onset,
            "body_region_key": region,
        },
    )


def _medication(session, patient_id, name, dose, route, frequency, start, region, status="active"):
    insert_medication(
        session,
        {
            "id": _id(),
            "patient_id": patient_id,
            "name": name,
            "dose": dose,
            "route": route,
            "frequency": frequency,
            "status": status,
            "start_date": start,
            "body_region_key": region,
        },
    )


def _family(session, patient_id, relationship, condition, age):
    insert_family_history(
        session,
        {
            "id": _id(),
            "patient_id": patient_id,
            "relationship": relationship,
            "condition": condition,
            "age_at_diagnosis": age,
        },
    )


def _series(session, patient_id, name, unit, region, points):
    for observed_at, value in points:
        insert_observation(
            session,
            {
                "id": _id(),
                "patient_id": patient_id,
                "name": name,
                "value": value,
                "unit": unit,
                "observed_at": observed_at,
                "source": "seed",
                "document_id": None,
                "body_region_key": region,
            },
        )


def _note(session, patient_id, body, created_at):
    insert_note(
        session,
        {
            "id": _id(),
            "patient_id": patient_id,
            "body": body,
            "embedding": None,
            "source_suggestion_id": None,
            "created_at": created_at,
        },
    )


def _visit(session, patient_id, occurred_at, summary):
    insert_encounter(
        session,
        {
            "id": _id(),
            "patient_id": patient_id,
            "encounter_type": "office_visit",
            "occurred_at": occurred_at,
            "summary": summary,
        },
    )


def _reminder(session, patient_id, rule_id, name, due_on, status="scheduled"):
    insert_reminder(
        session,
        {
            "id": _id(),
            "patient_id": patient_id,
            "rule_id": rule_id,
            "name": name,
            "due_on": due_on,
            "status": status,
        },
    )


def _jane(session, rules):
    _condition(session, JANE_ID, "Type 2 diabetes", "active", date(2022, 2, 10), "pancreas")
    _condition(session, JANE_ID, "Chronic kidney disease, stage 3a", "active", date(2025, 3, 4), "kidney")
    _medication(session, JANE_ID, "Metformin", "1000 mg", "oral", "twice daily", date(2022, 2, 11), "pancreas")
    _medication(session, JANE_ID, "Atorvastatin", "20 mg", "oral", "nightly", date(2024, 3, 5), "heart")
    _family(session, JANE_ID, "mother", "type 2 diabetes", 61)

    visits = [
        (_at(2023, 3, 2, 9), "Annual visit. Blood pressure above goal; lisinopril continued."),
        (_at(2023, 9, 14, 9), "Diabetes follow-up. A1c near goal on metformin."),
        (_at(2024, 3, 1, 9), "Annual visit. LDL 140; atorvastatin started."),
        (_at(2024, 9, 12, 9), "Diabetes follow-up. A1c drifting up."),
        (_at(2025, 3, 4, 9), "Annual visit. eGFR 58 with albuminuria; CKD stage 3a added."),
        (_at(2025, 9, 9, 9), "Diabetes follow-up. A1c 8.4; intensification discussed."),
    ]
    for occurred_at, summary in visits:
        _visit(session, JANE_ID, occurred_at, summary)

    _series(
        session, JANE_ID, "Systolic blood pressure", "mmHg", "heart",
        [(_at(2023, 3, 2, 9), 148), (_at(2023, 9, 14, 9), 142), (_at(2024, 3, 1, 9), 136),
         (_at(2024, 9, 12, 9), 134), (_at(2025, 3, 4, 9), 130), (_at(2025, 9, 9, 9), 128)],
    )
    _series(
        session, JANE_ID, "Diastolic blood pressure", "mmHg", "heart",
        [(_at(2023, 3, 2, 9), 92), (_at(2023, 9, 14, 9), 90), (_at(2024, 3, 1, 9), 86),
         (_at(2024, 9, 12, 9), 84), (_at(2025, 3, 4, 9), 82), (_at(2025, 9, 9, 9), 80)],
    )
    _series(
        session, JANE_ID, "A1c", "%", "pancreas",
        [(_at(2022, 2, 10), 7.9), (_at(2022, 8, 16), 7.4), (_at(2023, 3, 2), 7.1),
         (_at(2023, 9, 14), 7.3), (_at(2024, 3, 1), 7.6), (_at(2024, 9, 12), 7.8),
         (_at(2025, 3, 4), 8.1), (_at(2025, 9, 9), 8.4)],
    )
    _series(
        session, JANE_ID, "eGFR", "mL/min/1.73m2", "kidney",
        [(_at(2023, 3, 2), 78), (_at(2024, 3, 1), 68), (_at(2025, 3, 4), 58), (_at(2025, 9, 9), 56)],
    )
    _series(
        session, JANE_ID, "Creatinine", "mg/dL", "kidney",
        [(_at(2023, 3, 2), 0.9), (_at(2024, 3, 1), 1.0), (_at(2025, 3, 4), 1.2), (_at(2025, 9, 9), 1.3)],
    )
    _series(
        session, JANE_ID, "Urine albumin-creatinine ratio", "mg/g", "kidney",
        [(_at(2024, 3, 1), 38), (_at(2025, 3, 4), 64), (_at(2025, 9, 9), 71)],
    )
    _note(
        session,
        JANE_ID,
        "A1c has risen over three visits on metformin alone. Discussed adding a second agent; kidney function favours an SGLT2 inhibitor.",
        _at(2025, 9, 9, 12),
    )
    # Reminded already and still not scheduled: these are the open care gaps.
    _reminder(session, JANE_ID, rules["A1c recheck"], "A1c recheck", date(2025, 12, 9), status="sent")
    _reminder(session, JANE_ID, rules["Diabetic eye exam"], "Diabetic eye exam", date(2026, 3, 1), status="sent")
    _reminder(session, JANE_ID, rules["Mammography"], "Mammography", date(2026, 5, 1), status="sent")
    _reminder(session, JANE_ID, rules["Influenza vaccine"], "Influenza vaccine", date(2026, 10, 15))


def _john(session, rules):
    _condition(session, JOHN_ID, "Hypertension", "controlled", date(2020, 5, 20), "heart")
    _condition(session, JOHN_ID, "Hypothyroidism", "controlled", date(2016, 8, 9), "thyroid")
    _medication(session, JOHN_ID, "Amlodipine", "5 mg", "oral", "daily", date(2020, 5, 21), "heart")
    _medication(session, JOHN_ID, "Levothyroxine", "75 mcg", "oral", "daily", date(2016, 8, 10), "thyroid")

    for occurred_at, summary in (
        (_at(2023, 6, 5, 9), "Annual visit. Spirometry repeated; still smoking."),
        (_at(2024, 6, 3, 9), "Annual visit. Cessation counselling; declined pharmacotherapy."),
        (_at(2025, 6, 1, 9), "Annual visit. COPD stable; low-dose CT discussed."),
    ):
        _visit(session, JOHN_ID, occurred_at, summary)

    _series(session, JOHN_ID, "SpO2", "%", "lung", [(_at(2024, 6, 3), 95)])
    _series(
        session, JOHN_ID, "FEV1 percent predicted", "%", "lung",
        [(_at(2023, 6, 5), 62), (_at(2024, 6, 3), 60), (_at(2025, 6, 1), 59)],
    )
    _series(
        session, JOHN_ID, "Systolic blood pressure", "mmHg", "heart",
        [(_at(2024, 6, 3, 9), 132), (_at(2025, 6, 1, 9), 126)],
    )
    _series(session, JOHN_ID, "TSH", "mIU/L", "thyroid", [(_at(2024, 6, 3), 2.8), (_at(2025, 6, 1), 2.4)])
    _reminder(session, JOHN_ID, rules["Colorectal cancer screening"], "Colorectal cancer screening", date(2026, 6, 1))
    _reminder(session, JOHN_ID, rules["Influenza vaccine"], "Influenza vaccine", date(2026, 10, 15))


def _amy(session, rules):
    _condition(session, AMY_ID, "Iron deficiency anemia", "resolved", date(2024, 2, 6), "colon")
    _medication(
        session, AMY_ID, "Ferrous sulfate", "325 mg", "oral", "daily", date(2024, 2, 7), "colon", status="stopped"
    )
    for occurred_at, summary in (
        (_at(2024, 2, 6, 10), "Fatigue. Hemoglobin 10.8 with low ferritin; iron started."),
        (_at(2024, 8, 12, 10), "Anemia follow-up. Counts recovering."),
        (_at(2025, 8, 1, 10), "Annual visit. Anemia resolved; iron stopped."),
    ):
        _visit(session, AMY_ID, occurred_at, summary)
    _series(
        session, AMY_ID, "Hemoglobin", "g/dL", "colon",
        [(_at(2024, 2, 6), 10.8), (_at(2024, 8, 12), 12.1)],
    )
    _series(
        session, AMY_ID, "Ferritin", "ng/mL", "colon",
        [(_at(2024, 2, 6), 9), (_at(2024, 8, 12), 28), (_at(2025, 8, 1), 46)],
    )
    _reminder(session, AMY_ID, rules["Cervical cancer screening"], "Cervical cancer screening", date(2027, 4, 1))
