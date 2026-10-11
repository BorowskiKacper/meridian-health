import socket
from datetime import date, datetime, timezone
from urllib.parse import urlparse

from app.config import DATABASE_URL
from app.db.repositories import (
    get_body_region,
    get_coverage_by_patient,
    get_patient,
    list_appointments_by_patient,
    list_appointments_on,
    list_body_regions,
    list_conditions_by_patient,
    list_conditions_by_region,
    list_encounters_by_patient,
    list_family_history_by_patient,
    list_medications_by_patient,
    list_medications_by_region,
    list_notes_by_patient,
    list_observations_by_patient,
    list_observations_by_region,
    list_patients,
    list_reminder_rules,
    list_reminders_by_patient,
    list_specialty_focus,
    search_notes,
)
from expect import (
    APPOINTMENT_KEYS,
    BODY_REGION_KEYS,
    CONDITION_KEYS,
    COVERAGE_KEYS,
    ENCOUNTER_KEYS,
    FAMILY_HISTORY_KEYS,
    MEDICATION_KEYS,
    NOTE_KEYS,
    OBSERVATION_KEYS,
    PATIENT_KEYS,
    REMINDER_KEYS,
    REMINDER_RULE_KEYS,
    SPECIALTY_FOCUS_KEYS,
    UTC,
    assert_fields,
    assert_row_types,
)

JANE_ID = "11111111-1111-4111-8111-111111111111"
JOHN_ID = "22222222-2222-4222-8222-222222222222"
AMY_ID = "33333333-3333-4333-8333-333333333333"
PATIENT_IDS = {JANE_ID, JOHN_ID, AMY_ID}

JANE_OBSERVED_AT = datetime(2024, 3, 1, tzinfo=timezone.utc)
JANE_APPOINTMENT_START = datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc)
JANE_APPOINTMENT_END = datetime(2026, 10, 10, 15, 30, tzinfo=timezone.utc)
JOHN_APPOINTMENT_DAY = date(2026, 10, 11)


def _one(rows, label, predicate):
    assert isinstance(rows, list)
    matches = [row for row in rows if predicate(row)]
    assert len(matches) == 1, label
    return matches[0]


def _assert_patient_ids(patient_ids):
    assert isinstance(patient_ids, list)
    assert len(patient_ids) == 3
    assert set(patient_ids) == PATIENT_IDS
    assert all(isinstance(patient_id, str) for patient_id in patient_ids)


def test_seeded_db_uses_the_test_session(db, seeded_db):
    assert seeded_db.session is db
    _assert_patient_ids(seeded_db.patient_ids)


def test_seed_inserts_exactly_three_patients(seeded_db):
    session = seeded_db.session
    _assert_patient_ids(seeded_db.patient_ids)
    patients = list_patients(session)
    assert isinstance(patients, list)
    assert len(patients) == 3
    assert {row["id"] for row in patients} == PATIENT_IDS

    assert_fields(
        get_patient(session, JANE_ID),
        PATIENT_KEYS,
        id=JANE_ID,
        display_name="Jane Doe",
        date_of_birth=date(1974, 3, 15),
        sex="female",
        email_opt_in=True,
        email="jane.doe@example.com",
    )
    assert_fields(
        get_patient(session, JOHN_ID),
        PATIENT_KEYS,
        id=JOHN_ID,
        display_name="John Roe",
        email_opt_in=False,
        email="john.roe@example.com",
    )
    assert_fields(
        get_patient(session, AMY_ID),
        PATIENT_KEYS,
        id=AMY_ID,
        display_name="Amy Lee",
        email_opt_in=True,
        email="amy.lee@example.com",
    )


def test_each_seeded_patient_has_required_child_rows(seeded_db):
    session = seeded_db.session
    readers = (
        list_conditions_by_patient,
        list_medications_by_patient,
        list_family_history_by_patient,
        list_observations_by_patient,
        list_notes_by_patient,
        list_reminders_by_patient,
        list_appointments_by_patient,
    )
    for patient_id in PATIENT_IDS:
        for reader in readers:
            rows = reader(session, patient_id)
            assert isinstance(rows, list)
            assert rows
            assert all(row["patient_id"] == patient_id for row in rows)
        coverage = get_coverage_by_patient(session, patient_id)
        assert_fields(coverage, COVERAGE_KEYS, patient_id=patient_id)


def test_jane_doe_seed_rows(seeded_db):
    session = seeded_db.session

    condition = _one(
        list_conditions_by_patient(session, JANE_ID),
        "Jane Hypertension",
        lambda row: row["name"] == "Hypertension",
    )
    assert_fields(
        condition,
        CONDITION_KEYS,
        patient_id=JANE_ID,
        name="Hypertension",
        status="active",
        onset_date=date(2019, 4, 1),
        body_region_key="heart",
    )
    _assert_region_contains(
        list_conditions_by_region(session, JANE_ID, "heart"),
        list_conditions_by_region(session, JANE_ID, "lung"),
        condition["id"],
    )

    medication = _one(
        list_medications_by_patient(session, JANE_ID),
        "Jane Lisinopril",
        lambda row: row["name"] == "Lisinopril",
    )
    assert_fields(
        medication,
        MEDICATION_KEYS,
        patient_id=JANE_ID,
        name="Lisinopril",
        dose="10 mg",
        route="oral",
        frequency="daily",
        status="active",
        start_date=date(2019, 4, 2),
        body_region_key="heart",
    )
    _assert_region_contains(
        list_medications_by_region(session, JANE_ID, "heart"),
        list_medications_by_region(session, JANE_ID, "lung"),
        medication["id"],
    )

    history = _one(
        list_family_history_by_patient(session, JANE_ID),
        "Jane family history",
        lambda row: row["relationship"] == "father",
    )
    assert_fields(
        history,
        FAMILY_HISTORY_KEYS,
        patient_id=JANE_ID,
        relationship="father",
        condition="colorectal cancer",
        age_at_diagnosis=48,
    )

    observation = _one(
        list_observations_by_patient(session, JANE_ID),
        "Jane LDL",
        lambda row: row["name"] == "LDL",
    )
    assert_fields(
        observation,
        OBSERVATION_KEYS,
        patient_id=JANE_ID,
        name="LDL",
        value=140,
        unit="mg/dL",
        observed_at=JANE_OBSERVED_AT,
        source="seed",
        document_id=None,
        body_region_key="heart",
    )
    _assert_region_contains(
        list_observations_by_region(session, JANE_ID, "heart"),
        list_observations_by_region(session, JANE_ID, "lung"),
        observation["id"],
    )

    notes = list_notes_by_patient(session, JANE_ID)
    note = _one(
        notes,
        "Jane LDL note",
        lambda row: isinstance(row["body"], str) and "LDL" in row["body"],
    )
    assert_fields(
        note,
        NOTE_KEYS,
        patient_id=JANE_ID,
        embedding=None,
    )

    encounters = list_encounters_by_patient(session, JANE_ID)
    encounter = _one(
        encounters,
        "Jane colonoscopy",
        lambda row: row["encounter_type"] == "procedure"
        and isinstance(row["summary"], str)
        and "colonoscopy" in row["summary"].lower(),
    )
    assert_fields(
        encounter,
        ENCOUNTER_KEYS,
        patient_id=JANE_ID,
        encounter_type="procedure",
    )

    assert_fields(
        get_coverage_by_patient(session, JANE_ID),
        COVERAGE_KEYS,
        patient_id=JANE_ID,
        payer_name="Northwind Health",
        member_id="NW-1001",
        plan_name="PPO",
        active=True,
        deductible_remaining=400,
        copay=30,
        benefits=[{"name": "Preventive colonoscopy", "detail": "Covered in network"}],
    )

    rules = list_reminder_rules(session)
    rule = _one(
        rules,
        "colorectal screening rule",
        lambda row: row["name"] == "Colorectal cancer screening",
    )
    assert_fields(
        rule,
        REMINDER_RULE_KEYS,
        name="Colorectal cancer screening",
        baseline_age=45,
        guideline_source_id="uspstf:colorectal-cancer-screening",
    )
    reminders = list_reminders_by_patient(session, JANE_ID)
    reminder = _one(
        reminders,
        "Jane screening reminder",
        lambda row: row["name"] == "Colorectal cancer screening",
    )
    assert_fields(
        reminder,
        REMINDER_KEYS,
        patient_id=JANE_ID,
        rule_id=rule["id"],
        name="Colorectal cancer screening",
        due_on=date(2026, 10, 1),
        status="scheduled",
    )

    appointments = list_appointments_by_patient(session, JANE_ID)
    appointment = _one(
        appointments,
        "Jane follow-up",
        lambda row: isinstance(row["starts_at"], datetime)
        and row["starts_at"].tzinfo is not None
        and row["starts_at"].astimezone(UTC) == JANE_APPOINTMENT_START,
    )
    assert_fields(
        appointment,
        APPOINTMENT_KEYS,
        patient_id=JANE_ID,
        starts_at=JANE_APPOINTMENT_START,
        ends_at=JANE_APPOINTMENT_END,
        reason="Follow-up",
        status="scheduled",
    )
    on_day = list_appointments_on(session, date(2026, 10, 10))
    assert appointment["id"] in {row["id"] for row in on_day}
    assert all(row["starts_at"].astimezone(UTC).date() == date(2026, 10, 10) for row in on_day)


def _assert_region_contains(same_region, other_region, row_id):
    assert isinstance(same_region, list)
    assert isinstance(other_region, list)
    assert row_id in {row["id"] for row in same_region}
    assert all(row["patient_id"] == JANE_ID for row in same_region)
    assert all(row["body_region_key"] == "heart" for row in same_region)
    assert row_id not in {row["id"] for row in other_region}


def test_john_roe_and_amy_lee_seed_rows(seeded_db):
    session = seeded_db.session

    assert_fields(
        get_coverage_by_patient(session, JOHN_ID),
        COVERAGE_KEYS,
        patient_id=JOHN_ID,
        member_id="NW-1002",
    )
    john_appointments = list_appointments_by_patient(session, JOHN_ID)
    john_on_day = [
        row
        for row in john_appointments
        if row["starts_at"].astimezone(UTC).date() == JOHN_APPOINTMENT_DAY
    ]
    assert john_on_day
    on_eleventh = list_appointments_on(session, JOHN_APPOINTMENT_DAY)
    assert {row["id"] for row in john_on_day} <= {row["id"] for row in on_eleventh}
    assert all(
        row["starts_at"].astimezone(UTC).date() == JOHN_APPOINTMENT_DAY
        for row in on_eleventh
    )
    jane_ids = {
        row["id"] for row in list_appointments_by_patient(session, JANE_ID)
    }
    assert jane_ids.isdisjoint({row["id"] for row in on_eleventh})

    assert_fields(
        get_coverage_by_patient(session, AMY_ID),
        COVERAGE_KEYS,
        patient_id=AMY_ID,
        member_id="NW-1003",
    )
    amy_reminder = _one(
        list_reminders_by_patient(session, AMY_ID),
        "Amy scheduled reminder",
        lambda row: row["status"] == "scheduled" and row["due_on"] == date(2026, 9, 1),
    )
    assert_fields(
        amy_reminder,
        REMINDER_KEYS,
        patient_id=AMY_ID,
        due_on=date(2026, 9, 1),
        status="scheduled",
    )


def test_seed_body_regions_and_specialty_focus(seeded_db):
    session = seeded_db.session
    heart = get_body_region(session, "heart")
    assert_fields(
        heart,
        BODY_REGION_KEYS,
        region_key="heart",
        display_name="Heart",
        mesh_name="Heart",
    )
    regions = list_body_regions(session)
    assert isinstance(regions, list)
    assert {"heart", "lung", "colon"} <= {row["region_key"] for row in regions}
    assert all(set(row) == set(BODY_REGION_KEYS) for row in regions)
    for row in regions:
        assert_row_types(row)

    cardiology = list_specialty_focus(session, "cardiology")
    gastroenterology = list_specialty_focus(session, "gastroenterology")
    pulmonology = list_specialty_focus(session, "pulmonology")
    assert ("cardiology", "heart") in _pairs(cardiology)
    assert ("gastroenterology", "colon") in _pairs(gastroenterology)
    assert ("pulmonology", "lung") in _pairs(pulmonology)
    assert all(row["specialty_key"] == "cardiology" for row in cardiology)
    assert all(row["specialty_key"] == "gastroenterology" for row in gastroenterology)
    assert all(row["specialty_key"] == "pulmonology" for row in pulmonology)
    for rows in (cardiology, gastroenterology, pulmonology):
        assert rows
        for row in rows:
            assert set(row) == set(SPECIALTY_FOCUS_KEYS)
            assert_row_types(row)


def _pairs(rows):
    assert isinstance(rows, list)
    return {(row["specialty_key"], row["region_key"]) for row in rows}


def test_seeded_notes_have_no_embedding_and_jane_ldl_is_searchable(seeded_db):
    session = seeded_db.session
    for patient_id in PATIENT_IDS:
        notes = list_notes_by_patient(session, patient_id)
        assert notes
        for note in notes:
            assert_fields(note, NOTE_KEYS, patient_id=patient_id, embedding=None)

    found = search_notes(session, JANE_ID, "LDL")
    assert isinstance(found, list)
    assert found
    assert all(row["patient_id"] == JANE_ID for row in found)
    assert any("LDL" in row["body"] and row["embedding"] is None for row in found)
    other_note_ids = set()
    for patient_id in (JOHN_ID, AMY_ID):
        other_note_ids.update(
            row["id"] for row in list_notes_by_patient(session, patient_id)
        )
    assert other_note_ids.isdisjoint({row["id"] for row in found})


def test_seed_does_not_call_an_agent_or_vendor(db, seed_fn, monkeypatch):
    allowed_host = urlparse(DATABASE_URL).hostname
    real_create_connection = socket.create_connection

    def guarded_create_connection(address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if host != allowed_host:
            raise AssertionError("seed called an agent or a vendor")
        return real_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    _assert_patient_ids(seed_fn(db))
