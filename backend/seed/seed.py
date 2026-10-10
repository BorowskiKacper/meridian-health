"""Load the demo patients into a session the caller already opened."""

from datetime import date, datetime, timezone
from uuid import uuid4

from app.db.repositories import (
    insert_appointment,
    insert_body_region,
    insert_condition,
    insert_coverage,
    insert_encounter,
    insert_family_history,
    insert_medication,
    insert_note,
    insert_observation,
    insert_patient,
    insert_reminder,
    insert_reminder_rule,
    insert_specialty_focus,
)

JANE_ID = "11111111-1111-4111-8111-111111111111"
JOHN_ID = "22222222-2222-4222-8222-222222222222"
AMY_ID = "33333333-3333-4333-8333-333333333333"

_UTC = timezone.utc


def _id():
    return str(uuid4())


def _at(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=_UTC)


def seed(session):
    _seed_reference(session)
    screening_rule_id = _seed_rule(
        session,
        "Colorectal cancer screening",
        45,
        "uspstf:colorectal-cancer-screening",
    )
    _seed_jane(session, screening_rule_id)
    _seed_john(session)
    _seed_amy(session)
    return [JANE_ID, JOHN_ID, AMY_ID]


def _seed_reference(session):
    for region_key, display_name, mesh_name in (
        ("heart", "Heart", "Heart"),
        ("lung", "Lung", "Lung"),
        ("colon", "Colon", "Colon"),
    ):
        insert_body_region(
            session,
            {
                "region_key": region_key,
                "display_name": display_name,
                "mesh_name": mesh_name,
            },
        )
    for specialty_key, region_key in (
        ("cardiology", "heart"),
        ("gastroenterology", "colon"),
        ("pulmonology", "lung"),
    ):
        insert_specialty_focus(
            session,
            {"specialty_key": specialty_key, "region_key": region_key},
        )


def _seed_rule(session, name, baseline_age, guideline_source_id):
    rule = insert_reminder_rule(
        session,
        {
            "id": _id(),
            "name": name,
            "baseline_age": baseline_age,
            "guideline_source_id": guideline_source_id,
        },
    )
    return rule["id"]


def _seed_jane(session, screening_rule_id):
    insert_patient(
        session,
        {
            "id": JANE_ID,
            "display_name": "Jane Doe",
            "date_of_birth": date(1974, 3, 15),
            "sex": "female",
            "sms_opt_in": True,
            "phone_e164": "+15555550101",
        },
    )
    insert_condition(
        session,
        {
            "id": _id(),
            "patient_id": JANE_ID,
            "name": "Hypertension",
            "status": "active",
            "onset_date": date(2019, 4, 1),
            "body_region_key": "heart",
        },
    )
    insert_medication(
        session,
        {
            "id": _id(),
            "patient_id": JANE_ID,
            "name": "Lisinopril",
            "dose": "10 mg",
            "route": "oral",
            "frequency": "daily",
            "status": "active",
            "start_date": date(2019, 4, 2),
            "body_region_key": "heart",
        },
    )
    insert_family_history(
        session,
        {
            "id": _id(),
            "patient_id": JANE_ID,
            "relationship": "father",
            "condition": "colorectal cancer",
            "age_at_diagnosis": 48,
        },
    )
    insert_observation(
        session,
        {
            "id": _id(),
            "patient_id": JANE_ID,
            "name": "LDL",
            "value": 140,
            "unit": "mg/dL",
            "observed_at": _at(2024, 3, 1),
            "source": "seed",
            "document_id": None,
            "body_region_key": "heart",
        },
    )
    insert_note(
        session,
        {
            "id": _id(),
            "patient_id": JANE_ID,
            "body": "LDL is above the patient's goal.",
            "embedding": None,
            "source_suggestion_id": None,
            "created_at": _at(2024, 3, 1, 12),
        },
    )
    insert_encounter(
        session,
        {
            "id": _id(),
            "patient_id": JANE_ID,
            "encounter_type": "procedure",
            "occurred_at": _at(2024, 6, 1, 15),
            "summary": "Screening colonoscopy",
        },
    )
    insert_coverage(
        session,
        {
            "id": _id(),
            "patient_id": JANE_ID,
            "payer_name": "Northwind Health",
            "member_id": "NW-1001",
            "plan_name": "PPO",
            "active": True,
            "deductible_remaining": 400,
            "copay": 30,
            "benefits": [
                {"name": "Preventive colonoscopy", "detail": "Covered in network"}
            ],
        },
    )
    insert_reminder(
        session,
        {
            "id": _id(),
            "patient_id": JANE_ID,
            "rule_id": screening_rule_id,
            "name": "Colorectal cancer screening",
            "due_on": date(2026, 10, 1),
            "status": "scheduled",
        },
    )
    insert_appointment(
        session,
        {
            "id": _id(),
            "patient_id": JANE_ID,
            "starts_at": _at(2026, 10, 10, 15, 0),
            "ends_at": _at(2026, 10, 10, 15, 30),
            "reason": "Follow-up",
            "status": "scheduled",
        },
    )


def _seed_john(session):
    rule_id = _seed_rule(
        session,
        "Lung cancer screening",
        50,
        "uspstf:lung-cancer-screening",
    )
    insert_patient(
        session,
        {
            "id": JOHN_ID,
            "display_name": "John Roe",
            "date_of_birth": date(1968, 11, 2),
            "sex": "male",
            "sms_opt_in": False,
            "phone_e164": "+15555550102",
        },
    )
    insert_condition(
        session,
        {
            "id": _id(),
            "patient_id": JOHN_ID,
            "name": "COPD",
            "status": "active",
            "onset_date": date(2018, 1, 15),
            "body_region_key": "lung",
        },
    )
    insert_medication(
        session,
        {
            "id": _id(),
            "patient_id": JOHN_ID,
            "name": "Tiotropium",
            "dose": "18 mcg",
            "route": "inhaled",
            "frequency": "daily",
            "status": "active",
            "start_date": date(2018, 1, 16),
            "body_region_key": "lung",
        },
    )
    insert_family_history(
        session,
        {
            "id": _id(),
            "patient_id": JOHN_ID,
            "relationship": "mother",
            "condition": "asthma",
            "age_at_diagnosis": 55,
        },
    )
    insert_observation(
        session,
        {
            "id": _id(),
            "patient_id": JOHN_ID,
            "name": "SpO2",
            "value": 96,
            "unit": "%",
            "observed_at": _at(2025, 6, 1),
            "source": "seed",
            "document_id": None,
            "body_region_key": "lung",
        },
    )
    insert_note(
        session,
        {
            "id": _id(),
            "patient_id": JOHN_ID,
            "body": "Breathing is stable on the current inhaler.",
            "embedding": None,
            "source_suggestion_id": None,
            "created_at": _at(2025, 6, 1, 12),
        },
    )
    insert_coverage(
        session,
        {
            "id": _id(),
            "patient_id": JOHN_ID,
            "payer_name": "Northwind Health",
            "member_id": "NW-1002",
            "plan_name": "HMO",
            "active": True,
            "deductible_remaining": 250,
            "copay": 20,
            "benefits": [{"name": "Specialist visit", "detail": "Covered in network"}],
        },
    )
    insert_reminder(
        session,
        {
            "id": _id(),
            "patient_id": JOHN_ID,
            "rule_id": rule_id,
            "name": "Lung cancer screening",
            "due_on": date(2026, 11, 1),
            "status": "scheduled",
        },
    )
    insert_appointment(
        session,
        {
            "id": _id(),
            "patient_id": JOHN_ID,
            "starts_at": _at(2026, 10, 11, 15, 0),
            "ends_at": _at(2026, 10, 11, 15, 30),
            "reason": "Pulmonary follow-up",
            "status": "scheduled",
        },
    )


def _seed_amy(session):
    rule_id = _seed_rule(
        session,
        "Follow-up labs",
        40,
        "uspstf:lipid-disorders-screening",
    )
    insert_patient(
        session,
        {
            "id": AMY_ID,
            "display_name": "Amy Lee",
            "date_of_birth": date(1988, 5, 2),
            "sex": "female",
            "sms_opt_in": True,
            "phone_e164": "+15555550103",
        },
    )
    insert_condition(
        session,
        {
            "id": _id(),
            "patient_id": AMY_ID,
            "name": "Diverticulosis",
            "status": "active",
            "onset_date": date(2021, 9, 1),
            "body_region_key": "colon",
        },
    )
    insert_medication(
        session,
        {
            "id": _id(),
            "patient_id": AMY_ID,
            "name": "Psyllium",
            "dose": "1 packet",
            "route": "oral",
            "frequency": "daily",
            "status": "active",
            "start_date": date(2021, 9, 2),
            "body_region_key": "colon",
        },
    )
    insert_family_history(
        session,
        {
            "id": _id(),
            "patient_id": AMY_ID,
            "relationship": "sister",
            "condition": "colon polyps",
            "age_at_diagnosis": 42,
        },
    )
    insert_observation(
        session,
        {
            "id": _id(),
            "patient_id": AMY_ID,
            "name": "Hemoglobin",
            "value": 13,
            "unit": "g/dL",
            "observed_at": _at(2025, 8, 1),
            "source": "seed",
            "document_id": None,
            "body_region_key": "colon",
        },
    )
    insert_note(
        session,
        {
            "id": _id(),
            "patient_id": AMY_ID,
            "body": "Diet and activity were discussed.",
            "embedding": None,
            "source_suggestion_id": None,
            "created_at": _at(2025, 8, 1, 12),
        },
    )
    insert_coverage(
        session,
        {
            "id": _id(),
            "patient_id": AMY_ID,
            "payer_name": "Northwind Health",
            "member_id": "NW-1003",
            "plan_name": "PPO",
            "active": True,
            "deductible_remaining": 100,
            "copay": 25,
            "benefits": [{"name": "Lab work", "detail": "Covered in network"}],
        },
    )
    insert_reminder(
        session,
        {
            "id": _id(),
            "patient_id": AMY_ID,
            "rule_id": rule_id,
            "name": "Follow-up labs",
            "due_on": date(2026, 9, 1),
            "status": "scheduled",
        },
    )
    insert_appointment(
        session,
        {
            "id": _id(),
            "patient_id": AMY_ID,
            "starts_at": _at(2026, 10, 12, 16, 0),
            "ends_at": _at(2026, 10, 12, 16, 30),
            "reason": "Gastroenterology follow-up",
            "status": "scheduled",
        },
    )
