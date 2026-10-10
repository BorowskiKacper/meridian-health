from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import DataError

from app.db.repositories import (
    get_appointment,
    get_body_region,
    get_coverage_by_patient,
    get_patient,
    get_reminder,
    get_request,
    get_sms_message_by_sid,
    get_suggestion,
    insert_appointment,
    insert_audit_log,
    insert_body_region,
    insert_condition,
    insert_coverage,
    insert_document,
    insert_eligibility_check,
    insert_encounter,
    insert_family_history,
    insert_medication,
    insert_note,
    insert_observation,
    insert_patient,
    insert_reminder,
    insert_reminder_rule,
    insert_request,
    insert_sms_message,
    insert_specialty_focus,
    insert_suggestion,
    list_appointments_by_patient,
    list_appointments_on,
    list_audit_logs_by_patient,
    list_body_regions,
    list_conditions_by_patient,
    list_conditions_by_region,
    list_documents_by_patient,
    list_eligibility_checks_by_patient,
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
    list_suggestions,
    search_notes,
    update_appointment,
    update_condition,
    update_family_history,
    update_medication,
    update_note,
    update_observation,
    update_patient,
    update_reminder,
    update_sms_message,
    update_suggestion,
)
from expect import assert_contract
from rows import (
    appointment_row,
    audit_log_row,
    body_region_row,
    condition_row,
    coverage_row,
    document_row,
    eligibility_check_row,
    embedding768,
    encounter_row,
    family_history_row,
    medication_row,
    note_row,
    observation_row,
    patient_row,
    reminder_row,
    reminder_rule_row,
    request_row,
    sms_message_row,
    specialty_focus_row,
    suggestion_row,
)

UTC = timezone.utc


def ids(rows):
    assert isinstance(rows, list)
    return {row["id"] for row in rows}


def sole(rows, expected):
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert_contract(rows[0], expected)
    return rows[0]


def insert_owner(db, **overrides):
    row = patient_row(**overrides)
    assert_contract(insert_patient(db, row), row)
    return row


def insert_region(db, region_key, display_name, mesh_name):
    row = body_region_row(region_key, display_name, mesh_name)
    assert_contract(insert_body_region(db, row), row)
    return row


def insert_saved_request(db, patient_id):
    row = request_row(patient_id)
    assert_contract(insert_request(db, row), row)
    assert_contract(get_request(db, row["id"]), row)
    return row


def insert_saved_suggestion(db, patient_id, **overrides):
    request = insert_saved_request(db, patient_id)
    row = suggestion_row(patient_id, request["id"], **overrides)
    assert_contract(insert_suggestion(db, row), row)
    assert "unconfirmed" not in row
    return row


def test_patient_round_trip_and_sms_opt_in_update(db):
    row = patient_row()
    assert_contract(insert_patient(db, row), row)
    assert_contract(get_patient(db, row["id"]), row)

    expected = {**row, "sms_opt_in": False}
    assert_contract(update_patient(db, row["id"], {"sms_opt_in": False}), expected)
    assert_contract(get_patient(db, row["id"]), expected)
    assert sole(list_patients(db), expected)


def test_condition_round_trip_and_update(db):
    owner = insert_owner(db)
    insert_region(db, "heart", "Heart", "Heart")
    row = condition_row(owner["id"])
    assert_contract(insert_condition(db, row), row)
    assert sole(list_conditions_by_patient(db, owner["id"]), row)

    expected = {**row, "status": "controlled"}
    assert_contract(update_condition(db, row["id"], {"status": "controlled"}), expected)
    assert sole(list_conditions_by_patient(db, owner["id"]), expected)


def test_medication_round_trip_and_update(db):
    owner = insert_owner(db)
    insert_region(db, "heart", "Heart", "Heart")
    row = medication_row(owner["id"])
    assert_contract(insert_medication(db, row), row)
    assert sole(list_medications_by_patient(db, owner["id"]), row)

    expected = {**row, "dose": "20 mg"}
    assert_contract(update_medication(db, row["id"], {"dose": "20 mg"}), expected)
    assert sole(list_medications_by_patient(db, owner["id"]), expected)


def test_family_history_round_trip_and_update(db):
    owner = insert_owner(db)
    row = family_history_row(owner["id"])
    assert_contract(insert_family_history(db, row), row)
    assert sole(list_family_history_by_patient(db, owner["id"]), row)

    expected = {**row, "age_at_diagnosis": 50}
    assert_contract(
        update_family_history(db, row["id"], {"age_at_diagnosis": 50}),
        expected,
    )
    assert sole(list_family_history_by_patient(db, owner["id"]), expected)


def test_observation_round_trip_and_update(db):
    owner = insert_owner(db)
    insert_region(db, "heart", "Heart", "Heart")
    document = document_row(owner["id"])
    assert_contract(insert_document(db, document), document)
    row = observation_row(owner["id"], document_id=document["id"], source="lab_report")
    assert_contract(insert_observation(db, row), row)
    assert sole(list_observations_by_patient(db, owner["id"]), row)

    expected = {**row, "value": 128}
    assert_contract(update_observation(db, row["id"], {"value": 128}), expected)
    assert sole(list_observations_by_patient(db, owner["id"]), expected)


def test_encounter_round_trip(db):
    owner = insert_owner(db)
    row = encounter_row(owner["id"])
    assert_contract(insert_encounter(db, row), row)
    assert sole(list_encounters_by_patient(db, owner["id"]), row)


def test_document_round_trip(db):
    owner = insert_owner(db)
    row = document_row(owner["id"])
    assert_contract(insert_document(db, row), row)
    assert sole(list_documents_by_patient(db, owner["id"]), row)


def test_note_null_embedding_round_trip_and_update(db):
    owner = insert_owner(db)
    row = note_row(owner["id"], embedding=None, source_suggestion_id=None)
    assert_contract(insert_note(db, row), row)
    assert sole(list_notes_by_patient(db, owner["id"]), row)

    expected = {**row, "body": "LDL was reviewed with the patient."}
    assert_contract(
        update_note(db, row["id"], {"body": expected["body"]}),
        expected,
    )
    assert sole(list_notes_by_patient(db, owner["id"]), expected)


def test_note_768_embedding_round_trip(db):
    owner = insert_owner(db)
    suggestion = insert_saved_suggestion(
        db,
        owner["id"],
        target_table="notes",
        target_id=None,
        before={},
        after={"body": "Cholesterol remains above goal."},
    )
    row = note_row(
        owner["id"],
        body="Cholesterol remains above goal.",
        embedding=embedding768(),
        source_suggestion_id=suggestion["id"],
        created_at=datetime(2026, 2, 2, 16, 0, tzinfo=UTC),
    )
    assert_contract(insert_note(db, row), row)
    assert sole(list_notes_by_patient(db, owner["id"]), row)
    assert len(row["embedding"]) == 768


def test_note_embedding_other_length_is_rejected_by_the_database(db):
    owner = insert_owner(db)
    row = note_row(owner["id"], embedding=[0.5] * 767)
    with pytest.raises(DataError) as raised:
        insert_note(db, row)
        db.flush()
    message = f"{raised.value} {raised.value.orig}".lower()
    assert "dimension" in message
    assert "768" in message


def test_body_region_round_trip(db):
    row = body_region_row("heart", "Heart", "Heart")
    assert_contract(insert_body_region(db, row), row)
    assert_contract(get_body_region(db, "heart"), row)
    assert sole(list_body_regions(db), row)


def test_specialty_focus_round_trip(db):
    insert_region(db, "heart", "Heart", "Heart")
    row = specialty_focus_row("cardiology", "heart")
    assert_contract(insert_specialty_focus(db, row), row)
    assert sole(list_specialty_focus(db, "cardiology"), row)


def test_reminder_rule_round_trip(db):
    row = reminder_rule_row()
    assert_contract(insert_reminder_rule(db, row), row)
    assert sole(list_reminder_rules(db), row)


def test_reminder_round_trip_and_update(db):
    owner = insert_owner(db)
    rule = reminder_rule_row()
    assert_contract(insert_reminder_rule(db, rule), rule)
    row = reminder_row(owner["id"], rule["id"])
    assert_contract(insert_reminder(db, row), row)
    assert_contract(get_reminder(db, row["id"]), row)
    assert sole(list_reminders_by_patient(db, owner["id"]), row)

    expected = {**row, "due_on": date(2026, 11, 1)}
    assert_contract(
        update_reminder(db, row["id"], {"due_on": expected["due_on"]}),
        expected,
    )
    assert_contract(get_reminder(db, row["id"]), expected)


def test_request_round_trip(db):
    owner = insert_owner(db)
    row = request_row(
        owner["id"],
        channel="voice",
        role="secretary",
        route="secretary",
        transcript="When is the next opening?",
    )
    assert_contract(insert_request(db, row), row)
    assert_contract(get_request(db, row["id"]), row)


def test_suggestion_round_trip_and_update(db):
    owner = insert_owner(db)
    insert_region(db, "heart", "Heart", "Heart")
    condition = condition_row(owner["id"])
    assert_contract(insert_condition(db, condition), condition)
    request = insert_saved_request(db, owner["id"])
    row = suggestion_row(
        owner["id"],
        request["id"],
        target_table="conditions",
        target_id=condition["id"],
    )
    saved = insert_suggestion(db, row)
    assert_contract(saved, row)
    assert "unconfirmed" not in saved
    assert_contract(get_suggestion(db, row["id"]), row)
    assert sole(list_suggestions(db, owner["id"]), row)

    expected = {**row, "status": "approved"}
    updated = update_suggestion(db, row["id"], {"status": "approved"})
    assert_contract(updated, expected)
    assert "unconfirmed" not in updated
    assert_contract(get_suggestion(db, row["id"]), expected)


def test_audit_log_round_trip(db):
    owner = insert_owner(db)
    suggestion = insert_saved_suggestion(db, owner["id"])
    row = audit_log_row(owner["id"], suggestion["id"])
    assert_contract(insert_audit_log(db, row), row)
    assert sole(list_audit_logs_by_patient(db, owner["id"]), row)


def test_sms_message_round_trip_and_update(db):
    owner = insert_owner(db)
    rule = reminder_rule_row(name="Blood pressure check")
    assert_contract(insert_reminder_rule(db, rule), rule)
    reminder = reminder_row(owner["id"], rule["id"], name="Blood pressure check")
    assert_contract(insert_reminder(db, reminder), reminder)
    row = sms_message_row(owner["id"], reminder["id"], to_phone=owner["phone_e164"])
    assert_contract(insert_sms_message(db, row), row)
    assert_contract(get_sms_message_by_sid(db, row["twilio_sid"]), row)

    expected = {**row, "status": "sent"}
    assert_contract(update_sms_message(db, row["id"], {"status": "sent"}), expected)
    assert_contract(get_sms_message_by_sid(db, row["twilio_sid"]), expected)


def test_coverage_round_trip(db):
    owner = insert_owner(db)
    row = coverage_row(owner["id"])
    assert_contract(insert_coverage(db, row), row)
    assert_contract(get_coverage_by_patient(db, owner["id"]), row)


def test_eligibility_check_round_trip(db):
    owner = insert_owner(db)
    coverage = coverage_row(owner["id"])
    assert_contract(insert_coverage(db, coverage), coverage)
    row = eligibility_check_row(owner["id"], coverage["id"])
    assert_contract(insert_eligibility_check(db, row), row)
    assert sole(list_eligibility_checks_by_patient(db, owner["id"]), row)


def test_appointment_round_trip_and_update(db):
    owner = insert_owner(db)
    starts_at = datetime(2026, 10, 10, 15, 0, tzinfo=UTC)
    row = appointment_row(owner["id"], starts_at)
    assert_contract(insert_appointment(db, row), row)
    assert_contract(get_appointment(db, row["id"]), row)
    assert sole(list_appointments_by_patient(db, owner["id"]), row)
    assert sole(list_appointments_on(db, date(2026, 10, 10)), row)

    expected = {**row, "status": "completed"}
    assert_contract(
        update_appointment(db, row["id"], {"status": "completed"}),
        expected,
    )
    assert_contract(get_appointment(db, row["id"]), expected)


def test_region_lists_are_scoped_to_one_patient_and_region(db):
    first = insert_owner(db, display_name="First Patient")
    second = insert_owner(db, display_name="Second Patient")
    insert_region(db, "heart", "Heart", "Heart")
    insert_region(db, "lung", "Lung", "Lung")

    heart_condition = condition_row(first["id"], body_region_key="heart")
    lung_condition = condition_row(
        first["id"],
        name="Asthma",
        body_region_key="lung",
    )
    other_condition = condition_row(second["id"], body_region_key="heart")
    insert_condition(db, heart_condition)
    insert_condition(db, lung_condition)
    insert_condition(db, other_condition)

    heart_medication = medication_row(first["id"], body_region_key="heart")
    lung_medication = medication_row(
        first["id"],
        name="Albuterol",
        body_region_key="lung",
    )
    other_medication = medication_row(second["id"], body_region_key="heart")
    insert_medication(db, heart_medication)
    insert_medication(db, lung_medication)
    insert_medication(db, other_medication)

    heart_observation = observation_row(first["id"], body_region_key="heart")
    lung_observation = observation_row(
        first["id"],
        name="SpO2",
        value=97,
        unit="%",
        body_region_key="lung",
        source="chart",
    )
    other_observation = observation_row(second["id"], body_region_key="heart")
    insert_observation(db, heart_observation)
    insert_observation(db, lung_observation)
    insert_observation(db, other_observation)

    conditions = list_conditions_by_region(db, first["id"], "heart")
    medications = list_medications_by_region(db, first["id"], "heart")
    observations = list_observations_by_region(db, first["id"], "heart")

    assert sole(conditions, heart_condition)
    assert sole(medications, heart_medication)
    assert sole(observations, heart_observation)
    assert lung_condition["id"] not in ids(conditions)
    assert other_condition["id"] not in ids(conditions)
    assert lung_medication["id"] not in ids(medications)
    assert other_medication["id"] not in ids(medications)
    assert lung_observation["id"] not in ids(observations)
    assert other_observation["id"] not in ids(observations)


def test_search_notes_finds_null_embedding_for_that_patient(db):
    owner = insert_owner(db)
    other = insert_owner(db, display_name="Other Patient")
    match = note_row(
        owner["id"],
        body="The LDL result is high.",
        embedding=None,
    )
    same_patient_other = note_row(
        owner["id"],
        body="Blood pressure is controlled.",
        embedding=embedding768(),
    )
    other_patient = note_row(
        other["id"],
        body="Repeat the LDL panel.",
        embedding=None,
    )
    insert_note(db, match)
    insert_note(db, same_patient_other)
    insert_note(db, other_patient)

    found = search_notes(db, owner["id"], "LDL")
    assert isinstance(found, list)
    assert ids(found) == {match["id"]}
    assert sole(found, match)
    assert found[0]["embedding"] is None
    assert other_patient["id"] not in ids(found)


def test_list_appointments_on_uses_utc_calendar_date(db):
    owner = insert_owner(db)
    eastern = timezone(timedelta(hours=-4))
    on_tenth = [
        appointment_row(owner["id"], datetime(2026, 10, 10, 15, 0, tzinfo=UTC)),
        appointment_row(owner["id"], datetime(2026, 10, 10, 23, 45, tzinfo=UTC)),
        appointment_row(
            owner["id"],
            datetime(2026, 10, 9, 21, 0, tzinfo=eastern),
            reason="Early UTC follow-up",
        ),
    ]
    on_eleventh = [
        appointment_row(
            owner["id"],
            datetime(2026, 10, 11, 0, 15, tzinfo=UTC),
            reason="Next day",
        ),
        appointment_row(
            owner["id"],
            datetime(2026, 10, 10, 21, 0, tzinfo=eastern),
            reason="Local evening",
        ),
    ]
    for row in on_tenth + on_eleventh:
        assert_contract(insert_appointment(db, row), row)

    tenth = list_appointments_on(db, date(2026, 10, 10))
    eleventh = list_appointments_on(db, date(2026, 10, 11))
    assert ids(tenth) == {row["id"] for row in on_tenth}
    assert ids(eleventh) == {row["id"] for row in on_eleventh}
    assert all(
        row["starts_at"].astimezone(UTC).date() == date(2026, 10, 10) for row in tenth
    )
    assert all(
        row["starts_at"].astimezone(UTC).date() == date(2026, 10, 11)
        for row in eleventh
    )


def test_list_suggestions_filters_by_status(db):
    owner = insert_owner(db)
    other = insert_owner(db, display_name="Other Patient")
    pending = insert_saved_suggestion(db, owner["id"], status="pending")
    approved = insert_saved_suggestion(
        db,
        owner["id"],
        status="approved",
        reason="Added after the visit.",
        confidence=1.0,
        citations=[],
        validation_flags=[],
        source="lab_report",
    )
    other_pending = insert_saved_suggestion(db, other["id"], status="pending")

    pending_rows = list_suggestions(db, owner["id"], status="pending")
    approved_rows = list_suggestions(db, owner["id"], status="approved")
    all_rows = list_suggestions(db, owner["id"])
    explicit_all = list_suggestions(db, owner["id"], status=None)

    assert ids(pending_rows) == {pending["id"]}
    assert sole(pending_rows, pending)
    assert ids(approved_rows) == {approved["id"]}
    assert sole(approved_rows, approved)
    assert ids(all_rows) == {pending["id"], approved["id"]}
    assert ids(explicit_all) == {pending["id"], approved["id"]}
    assert list_suggestions(db, owner["id"], status="rejected") == []
    assert other_pending["id"] not in ids(all_rows)
    assert ids(list_suggestions(db, other["id"], status="pending")) == {
        other_pending["id"]
    }


def test_list_specialty_focus_does_not_return_another_specialty(db):
    insert_region(db, "heart", "Heart", "Heart")
    insert_region(db, "lung", "Lung", "Lung")
    cardiology = specialty_focus_row("cardiology", "heart")
    pulmonology = specialty_focus_row("pulmonology", "lung")
    insert_specialty_focus(db, cardiology)
    insert_specialty_focus(db, pulmonology)

    rows = list_specialty_focus(db, "cardiology")
    assert sole(rows, cardiology)
    assert all(row["specialty_key"] == "cardiology" for row in rows)
    assert pulmonology["region_key"] not in {row["region_key"] for row in rows}
