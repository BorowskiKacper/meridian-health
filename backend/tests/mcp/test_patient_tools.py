import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.db.repositories import (
    get_coverage_by_patient,
    get_patient,
    get_suggestion,
    insert_encounter,
    insert_patient,
    insert_suggestion,
    list_conditions_by_patient,
    list_encounters_by_patient,
    list_family_history_by_patient,
    list_medications_by_patient,
    list_notes_by_patient,
    list_observations_by_patient,
    list_reminders_by_patient,
    list_suggestions,
)
from app.mcp.tools import (
    get_coverage,
    get_patient_context,
    propose_change,
    search_patient_notes,
)

JANE_ID = "11111111-1111-4111-8111-111111111111"
AMY_ID = "33333333-3333-4333-8333-333333333333"
JANE_DOB = date(1974, 3, 15)
JANE_NOTE = "LDL is above the patient's goal."
AMY_DIET_NOTE = "Diet and activity were discussed."
JANE_LDL_OBSERVED_AT = "2024-03-01T00:00:00Z"
JANE_PROCEDURE_AT = "2024-06-01T15:00:00Z"
OFFICE_SUMMARY = "Office visit"
CONTEXT_KEYS = {
    "patient_id",
    "age",
    "allergies",
    "conditions",
    "medications",
    "recent_observations",
    "family_history",
    "past_procedures",
    "reminders",
    "pending_suggestions",
}
COVERAGE_KEYS = {
    "payer_name",
    "member_id",
    "plan_name",
    "active",
    "deductible_remaining",
    "copay",
    "benefits",
}
CITATION_KEYS = {"source_id", "title", "passage", "locator", "tier"}
NOTE_KEYS = {"id", "excerpt", "observed_labs"}
LAB_KEYS = {"id", "name", "value", "unit", "observed_at"}


def invoke(fn, *args, session, **kwargs):
    import inspect

    if "session" in inspect.signature(fn).parameters:
        kwargs["session"] = session
    return fn(*args, **kwargs)


def age_in_years(dob):
    today = datetime.now(timezone.utc).date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def assert_number(actual, expected):
    assert not isinstance(actual, bool)
    assert isinstance(actual, (int, float, Decimal))
    assert float(actual) == float(expected)


def assert_error(body, code, message_contains=None):
    assert isinstance(body, dict)
    assert set(body) == {"error"}
    error = body["error"]
    assert isinstance(error, dict)
    assert set(error) == {"code", "message"}
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert error["message"].strip()
    if message_contains is not None:
        assert message_contains in error["message"]


def assert_citation(citation):
    assert isinstance(citation, dict)
    assert set(citation) == CITATION_KEYS
    assert all(isinstance(citation[key], str) and citation[key] for key in CITATION_KEYS)


def citation_identity(citation):
    assert_citation(citation)
    return tuple(citation[key] for key in ("source_id", "title", "passage", "locator", "tier"))


def assert_same_citations(actual, expected):
    assert isinstance(actual, list)
    assert sorted(map(citation_identity, actual)) == sorted(map(citation_identity, expected))


def suggestion_snapshot(session, patient_id):
    return sorted(
        (row["id"], row["status"], row["kind"], row["target_table"])
        for row in list_suggestions(session, patient_id)
    )


def condition_snapshot(session, patient_id):
    return sorted(
        (row["id"], row["status"]) for row in list_conditions_by_patient(session, patient_id)
    )


def reminder_due_snapshot(session, patient_id):
    return sorted(row["due_on"] for row in list_reminders_by_patient(session, patient_id))


def jane_note(session):
    matches = [
        note
        for note in list_notes_by_patient(session, JANE_ID)
        if note["body"] == JANE_NOTE
    ]
    assert len(matches) == 1
    assert matches[0]["embedding"] is None
    return matches[0]


def jane_ldl(session):
    matches = [
        row
        for row in list_observations_by_patient(session, JANE_ID)
        if row["name"] == "LDL"
    ]
    assert len(matches) == 1
    return matches[0]


def baseline_citation():
    return {
        "source_id": "uspstf:colorectal-cancer-screening#2",
        "title": "USPSTF Colorectal Cancer: Screening: Clinician Summary",
        "passage": (
            "For adults aged 45 to 49 years: Screen adults aged 45 to 49 years "
            "for colorectal cancer. Grade B"
        ),
        "locator": (
            "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/"
            "colorectal-cancer-screening"
        ),
        "tier": "baseline",
    }


def literature_citation():
    return {
        "source_id": "pubmed:colorectal-family-history",
        "title": "Family history and earlier colorectal cancer screening",
        "passage": (
            "A first-degree relative diagnosed with colorectal cancer before age 60 "
            "supports starting screening before the average-risk age."
        ),
        "locator": "https://pubmed.ncbi.nlm.nih.gov/00000000/",
        "tier": "literature",
    }


def guideline_citation():
    return {
        "source_id": "acg:colorectal-cancer-screening",
        "title": "ACG colorectal cancer screening guideline",
        "passage": (
            "Patients with a first-degree relative diagnosed with colorectal cancer "
            "should begin screening earlier than average risk."
        ),
        "locator": "https://gi.org/guideline/colorectal-cancer-screening",
        "tier": "guideline",
    }


def web_citation():
    return {
        "source_id": "web:colorectal-screening-blog",
        "title": "A blog post about screening",
        "passage": "An unfiltered web page suggested changing the screening date.",
        "locator": "https://example.com/colorectal-screening",
        "tier": "web",
    }


def chart_citation(note):
    locator = f"note:{note['id']}"
    return {
        "source_id": locator,
        "title": "Chart note",
        "passage": note["body"],
        "locator": locator,
        "tier": "chart",
    }


def field_update(patient_id, citations, **overrides):
    suggestion = {
        "patient_id": patient_id,
        "request_id": None,
        "kind": "field_update",
        "status": "pending",
        "target_table": "conditions",
        "target_id": None,
        "before": {"status": "active"},
        "after": {"status": "controlled"},
        "reason": "Recent readings show the condition is controlled.",
        "confidence": 0.9,
        "citations": citations,
        "validation_flags": [],
        "source": "chart_agent",
    }
    suggestion.update(overrides)
    assert "id" not in suggestion
    return suggestion


def reminder_change(citations, after):
    suggestion = {
        "patient_id": JANE_ID,
        "request_id": None,
        "kind": "reminder_change",
        "status": "pending",
        "target_table": "reminder_schedule",
        "target_id": None,
        "before": {"due_on": "2026-10-01", "status": "scheduled"},
        "after": after,
        "reason": "Move the colorectal cancer screening reminder.",
        "confidence": 0.9,
        "citations": citations,
        "validation_flags": [],
        "source": "reminder_agent",
    }
    assert "id" not in suggestion
    return suggestion


def insert_chart_suggestion(session, status, reason):
    row = {
        "id": str(uuid.uuid4()),
        "patient_id": JANE_ID,
        "request_id": None,
        "kind": "field_update",
        "status": status,
        "target_table": "conditions",
        "target_id": None,
        "before": {"status": "active"},
        "after": {"status": "controlled"},
        "reason": reason,
        "confidence": 0.9,
        "citations": [],
        "validation_flags": [],
        "source": "chart_agent",
    }
    saved = insert_suggestion(session, row)
    assert saved["status"] == status
    return saved


def assert_ldl_lab(lab, observation_id):
    assert isinstance(lab, dict)
    assert set(lab) == LAB_KEYS
    assert lab["id"] == observation_id
    assert lab["name"] == "LDL"
    assert_number(lab["value"], 140)
    assert lab["unit"] == "mg/dL"
    assert lab["observed_at"] == JANE_LDL_OBSERVED_AT


def assert_note_hit(result, note, labs):
    assert isinstance(result, dict)
    assert set(result) == {"notes"}
    assert isinstance(result["notes"], list)
    assert len(result["notes"]) == 1
    hit = result["notes"][0]
    assert isinstance(hit, dict)
    assert set(hit) == NOTE_KEYS
    assert hit["id"] == note["id"]
    assert hit["excerpt"] == note["body"]
    assert isinstance(hit["observed_labs"], list)
    assert len(hit["observed_labs"]) == len(labs)
    for lab, observation in zip(hit["observed_labs"], labs):
        assert_ldl_lab(lab, observation["id"])


def assert_stored_suggestion(result, stored, suggestion):
    assert isinstance(result, dict)
    assert isinstance(result["id"], str)
    uuid.UUID(result["id"])
    assert result["id"] == stored["id"]
    assert result["status"] == "pending"
    assert stored["status"] == "pending"
    assert result["patient_id"] == suggestion["patient_id"]
    assert result["request_id"] is None
    assert stored["request_id"] is None
    assert result["kind"] == suggestion["kind"] == stored["kind"]
    assert result["target_table"] == suggestion["target_table"] == stored["target_table"]
    assert result["target_id"] is None
    assert stored["target_id"] is None
    assert result["before"] == suggestion["before"] == stored["before"]
    assert result["after"] == suggestion["after"] == stored["after"]
    assert result["reason"] == suggestion["reason"] == stored["reason"]
    assert_number(result["confidence"], suggestion["confidence"])
    assert_number(stored["confidence"], suggestion["confidence"])
    assert result["validation_flags"] == suggestion["validation_flags"] == []
    assert stored["validation_flags"] == []
    assert result["source"] == suggestion["source"] == stored["source"]
    assert_same_citations(result["citations"], suggestion["citations"])
    assert_same_citations(stored["citations"], suggestion["citations"])


def test_get_patient_context_returns_jane_chart(seeded_db):
    session = seeded_db.session
    patient = get_patient(session, JANE_ID)
    assert patient["date_of_birth"] == JANE_DOB
    assert patient["display_name"] == "Jane Doe"

    insert_encounter(
        session,
        {
            "id": str(uuid.uuid4()),
            "patient_id": JANE_ID,
            "encounter_type": "office",
            "occurred_at": datetime(2024, 7, 1, 15, 0, tzinfo=timezone.utc),
            "summary": OFFICE_SUMMARY,
        },
    )
    encounters = list_encounters_by_patient(session, JANE_ID)
    assert any(
        row["encounter_type"] == "procedure" and row["summary"] == "Screening colonoscopy"
        for row in encounters
    )
    assert any(
        row["encounter_type"] == "office" and row["summary"] == OFFICE_SUMMARY
        for row in encounters
    )

    pending = insert_chart_suggestion(session, "pending", "Pending chart update.")
    approved = insert_chart_suggestion(session, "approved", "Approved chart update.")
    assert [row["id"] for row in list_suggestions(session, JANE_ID, "pending")] == [
        pending["id"]
    ]
    assert [row["id"] for row in list_suggestions(session, JANE_ID, "approved")] == [
        approved["id"]
    ]

    result = invoke(get_patient_context, JANE_ID, session=session)

    assert isinstance(result, dict)
    assert set(result) == CONTEXT_KEYS
    assert result["patient_id"] == JANE_ID
    assert isinstance(result["patient_id"], str)
    assert type(result["age"]) is int
    assert result["age"] == age_in_years(patient["date_of_birth"])

    # Allergies reach every agent that drafts a chart or medication change.
    allergies = {row["substance"]: row for row in result["allergies"]}
    assert set(allergies) == {"Penicillin", "Shellfish"}
    assert allergies["Penicillin"]["severity"] == "moderate"
    assert allergies["Penicillin"]["reaction"] == "Hives"
    assert allergies["Penicillin"]["recorded_on"] == "2009-06-12"

    db_conditions = list_conditions_by_patient(session, JANE_ID)
    assert isinstance(result["conditions"], list)
    assert len(result["conditions"]) == len(db_conditions)
    hypertension = next(
        row for row in result["conditions"] if row["name"] == "Hypertension"
    )
    assert hypertension["status"] == "active"
    assert hypertension["onset_date"] == "2019-04-01"
    assert hypertension["body_region_key"] == "heart"

    db_medications = list_medications_by_patient(session, JANE_ID)
    assert isinstance(result["medications"], list)
    assert len(result["medications"]) == len(db_medications)
    assert any(row["name"] == "Lisinopril" for row in result["medications"])

    db_observations = list_observations_by_patient(session, JANE_ID)
    assert isinstance(result["recent_observations"], list)
    assert len(result["recent_observations"]) == len(db_observations)
    ldl = next(row for row in result["recent_observations"] if row["name"] == "LDL")
    assert_number(ldl["value"], 140)
    assert ldl["unit"] == "mg/dL"
    assert ldl["observed_at"] == JANE_LDL_OBSERVED_AT

    db_history = list_family_history_by_patient(session, JANE_ID)
    assert isinstance(result["family_history"], list)
    assert len(result["family_history"]) == len(db_history)
    father = next(row for row in result["family_history"] if row["relationship"] == "father")
    assert father["condition"] == "colorectal cancer"

    procedures = [
        row for row in encounters if row["encounter_type"] == "procedure"
    ]
    assert isinstance(result["past_procedures"], list)
    assert len(result["past_procedures"]) == len(procedures)
    assert {row["summary"] for row in result["past_procedures"]} == {
        row["summary"] for row in procedures
    }
    colonoscopy = result["past_procedures"][0]
    assert colonoscopy["summary"] == "Screening colonoscopy"
    assert colonoscopy["encounter_type"] == "procedure"
    assert colonoscopy["occurred_at"] == JANE_PROCEDURE_AT
    assert all(row["encounter_type"] == "procedure" for row in result["past_procedures"])
    assert OFFICE_SUMMARY not in {row["summary"] for row in result["past_procedures"]}

    db_reminders = list_reminders_by_patient(session, JANE_ID)
    assert isinstance(result["reminders"], list)
    assert len(result["reminders"]) == len(db_reminders)
    screening = next(
        row for row in result["reminders"] if row["name"] == "Colorectal cancer screening"
    )
    assert screening["due_on"] == "2026-10-01"
    assert screening["status"] == "scheduled"

    assert isinstance(result["pending_suggestions"], list)
    assert len(result["pending_suggestions"]) == 1
    item = result["pending_suggestions"][0]
    assert item["id"] == pending["id"]
    assert item["patient_id"] == JANE_ID
    assert item["kind"] == "field_update"
    assert item["status"] == "pending"
    assert item["target_table"] == "conditions"
    assert item["before"] == {"status": "active"}
    assert item["after"] == {"status": "controlled"}
    assert item["reason"] == pending["reason"]
    assert item["citations"] == []
    assert item["source"] == "chart_agent"
    assert item["unconfirmed"] is True
    assert approved["id"] not in {row["id"] for row in result["pending_suggestions"]}


def test_get_patient_context_unknown_patient_is_not_found(seeded_db):
    missing_id = str(uuid.uuid4())
    assert missing_id not in set(seeded_db.patient_ids)

    result = invoke(get_patient_context, missing_id, session=seeded_db.session)

    assert_error(result, "not_found", "Patient")


def test_search_patient_notes_returns_jane_ldl_note(seeded_db):
    session = seeded_db.session
    note = jane_note(session)
    observation = jane_ldl(session)

    result = invoke(search_patient_notes, JANE_ID, "LDL", session=session)

    assert_note_hit(result, note, [observation])
    assert "LDL" in result["notes"][0]["excerpt"]


def test_search_patient_notes_includes_ldl_when_excerpt_mentions_it(seeded_db):
    session = seeded_db.session
    note = jane_note(session)
    observation = jane_ldl(session)

    result = invoke(search_patient_notes, JANE_ID, "goal", session=session)

    assert_note_hit(result, note, [observation])
    assert "LDL" in result["notes"][0]["excerpt"]


def test_search_patient_notes_empty_when_text_is_absent(seeded_db):
    result = invoke(
        search_patient_notes,
        JANE_ID,
        "zzzz-no-such-text",
        session=seeded_db.session,
    )

    assert result == {"notes": []}


def test_search_patient_notes_amy_activity_omits_unmentioned_hemoglobin(seeded_db):
    session = seeded_db.session
    notes = [
        note
        for note in list_notes_by_patient(session, AMY_ID)
        if note["body"] == AMY_DIET_NOTE
    ]
    assert len(notes) == 1
    diet = notes[0]
    assert "activity" in diet["body"]
    assert "Hemoglobin" not in diet["body"]
    assert any(
        row["name"] == "Hemoglobin"
        for row in list_observations_by_patient(session, AMY_ID)
    )

    result = invoke(search_patient_notes, AMY_ID, "activity", session=session)

    assert isinstance(result, dict)
    assert set(result) == {"notes"}
    assert len(result["notes"]) == 1
    hit = result["notes"][0]
    assert set(hit) == NOTE_KEYS
    assert hit["id"] == diet["id"]
    assert hit["excerpt"] == diet["body"]
    assert hit["observed_labs"] == []
    assert "Hemoglobin" not in hit["excerpt"]


def test_get_coverage_returns_jane_plan(seeded_db):
    result = invoke(get_coverage, JANE_ID, session=seeded_db.session)

    assert isinstance(result, dict)
    assert set(result) == COVERAGE_KEYS
    assert result["payer_name"] == "Northwind Health"
    assert result["member_id"] == "NW-1001"
    assert result["plan_name"] == "PPO"
    assert result["active"] is True
    assert_number(result["deductible_remaining"], 400)
    assert_number(result["copay"], 30)
    assert result["benefits"] == [
        {"name": "Preventive colonoscopy", "detail": "Covered in network"}
    ]


def test_get_coverage_missing_row_is_not_found(seeded_db):
    session = seeded_db.session
    patient_id = str(uuid.uuid4())
    insert_patient(
        session,
        {
            "id": patient_id,
            "display_name": "No Coverage",
            "date_of_birth": date(1990, 1, 1),
            "sex": "female",
            "email_opt_in": False,
            "email": "nocoverage@example.com",
        },
    )
    assert get_patient(session, patient_id)["id"] == patient_id
    assert get_coverage_by_patient(session, patient_id) is None

    result = invoke(get_coverage, patient_id, session=session)

    assert_error(result, "not_found", "Coverage")


def test_propose_change_stores_pending_field_update_without_chart_write(seeded_db):
    session = seeded_db.session
    suggestion = field_update(JANE_ID, [chart_citation(jane_note(session))])
    before_conditions = condition_snapshot(session, JANE_ID)
    before_all = suggestion_snapshot(session, JANE_ID)
    before_pending = {row["id"] for row in list_suggestions(session, JANE_ID, "pending")}

    result = invoke(propose_change, JANE_ID, suggestion, session=session)

    after_pending = list_suggestions(session, JANE_ID, "pending")
    new_ids = {row["id"] for row in after_pending} - before_pending
    assert isinstance(result["id"], str)
    assert new_ids == {result["id"]}
    assert suggestion_snapshot(session, JANE_ID) != before_all
    stored = get_suggestion(session, result["id"])
    assert_stored_suggestion(result, stored, suggestion)
    assert condition_snapshot(session, JANE_ID) == before_conditions
    assert len(suggestion_snapshot(session, JANE_ID)) == len(before_all) + 1


def test_propose_change_stores_pending_reminder_change(seeded_db):
    session = seeded_db.session
    citations = [baseline_citation(), literature_citation()]
    suggestion = reminder_change(
        citations,
        {"due_on": "2026-12-01", "status": "scheduled"},
    )
    before_due = reminder_due_snapshot(session, JANE_ID)
    before_pending = {row["id"] for row in list_suggestions(session, JANE_ID, "pending")}

    result = invoke(propose_change, JANE_ID, suggestion, session=session)

    after_pending = list_suggestions(session, JANE_ID, "pending")
    new_ids = {row["id"] for row in after_pending} - before_pending
    assert new_ids == {result["id"]}
    stored = get_suggestion(session, result["id"])
    assert_stored_suggestion(result, stored, suggestion)
    assert stored["status"] == "pending"
    assert {item["tier"] for item in stored["citations"]} == {"baseline", "literature"}
    assert reminder_due_snapshot(session, JANE_ID) == before_due


@pytest.mark.parametrize(
    "case",
    [
        "patients_table",
        "after_key",
        "literature_only",
        "guideline_only",
        "no_citations",
        "web_tier",
    ],
)
def test_propose_change_refuses_without_inserting(seeded_db, case):
    session = seeded_db.session
    note = jane_note(session)
    if case == "patients_table":
        suggestion = field_update(
            JANE_ID,
            [chart_citation(note)],
            target_table="patients",
        )
    elif case == "after_key":
        suggestion = field_update(
            JANE_ID,
            [chart_citation(note)],
            after={"not_a_key": "x"},
        )
    elif case == "literature_only":
        suggestion = reminder_change([literature_citation()], {"due_on": "2026-12-01"})
    elif case == "guideline_only":
        suggestion = reminder_change([guideline_citation()], {"due_on": "2026-12-01"})
    elif case == "no_citations":
        suggestion = reminder_change([], {"due_on": "2026-12-01"})
    elif case == "web_tier":
        suggestion = field_update(
            JANE_ID,
            [chart_citation(note), baseline_citation(), web_citation()],
        )
    else:
        raise AssertionError(case)

    before = suggestion_snapshot(session, JANE_ID)
    result = invoke(propose_change, JANE_ID, suggestion, session=session)

    assert_error(result, "validation_error")
    assert suggestion_snapshot(session, JANE_ID) == before
