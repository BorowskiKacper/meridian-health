from pathlib import Path
from uuid import uuid4

from app.db.repositories import (
    get_suggestion,
    insert_suggestion,
    list_audit_logs_by_patient,
    list_conditions_by_patient,
    list_notes_by_patient,
)
from app.schemas import Suggestion
from app.services.approval import (
    approve_suggestions,
    create_plan_item,
    list_suggestions,
    reject_suggestions,
)

JANE_ID = "11111111-1111-4111-8111-111111111111"
AMY_ID = "33333333-3333-4333-8333-333333333333"

EMBEDDING = [0.1] * 768
REMINDER_ANSWER = "Screenings are up to date."
SOAP_BODY = "Hypertension is controlled."
PLAN_TEXT = "Recheck lipids in 6 weeks"
REJECT_REASON = "Not accurate"

CITATION = {
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

APPROVAL_SOURCE = (
    Path(__file__).resolve().parents[2] / "app" / "services" / "approval.py"
)


def invoke(fn, *args, session, **kwargs):
    import inspect

    if "session" in inspect.signature(fn).parameters:
        kwargs["session"] = session
    return fn(*args, **kwargs)


class Recording:
    def __init__(self):
        self.reminder_calls = []
        self.embed_calls = []
        self.follow_ups = []
        self.expect_approved_ids = ()
        self.expect_condition = None
        self.expect_note_body = None


def install_seams(monkeypatch):
    recording = Recording()

    def embed_text(body):
        recording.embed_calls.append(body)
        return [0.1] * 768

    def run_reminder_agent(patient_id, trigger, session=None):
        recording.reminder_calls.append((patient_id, trigger, session))
        for suggestion_id in recording.expect_approved_ids:
            stored = get_suggestion(session, suggestion_id)
            assert stored is not None
            assert stored["status"] == "approved"
        if recording.expect_condition is not None:
            condition_id, status = recording.expect_condition
            match = condition_by_id(session, condition_id)
            assert match["status"] == status
        if recording.expect_note_body is not None:
            bodies = [note["body"] for note in list_notes_by_patient(session, JANE_ID)]
            assert recording.expect_note_body in bodies
        follow_up = insert_suggestion(
            session,
            suggestion_row(
                patient_id=patient_id,
                reason="Screening schedule still fits.",
                confidence=0.4,
                source="reminder_agent",
            ),
        )
        recording.follow_ups.append(follow_up)
        return {"suggestions": [follow_up], "answer": REMINDER_ANSWER}

    monkeypatch.setattr(
        "app.services.approval.embed_text",
        embed_text,
        raising=False,
    )
    monkeypatch.setattr(
        "app.agents.doctor.run_reminder_agent",
        run_reminder_agent,
        raising=False,
    )
    return recording


def suggestion_row(**overrides):
    row = {
        "id": str(uuid4()),
        "patient_id": JANE_ID,
        "request_id": None,
        "kind": "field_update",
        "status": "pending",
        "target_table": "conditions",
        "target_id": None,
        "before": {"status": "active"},
        "after": {"status": "controlled"},
        "reason": "Recent readings show the condition is controlled.",
        "confidence": 0.9,
        "citations": [],
        "validation_flags": [],
        "source": "chart_agent",
    }
    row.update(overrides)
    return row


def save_suggestion(session, **overrides):
    return insert_suggestion(session, suggestion_row(**overrides))


def active_hypertension(session):
    matches = [
        row
        for row in list_conditions_by_patient(session, JANE_ID)
        if row["name"] == "Hypertension" and row["status"] == "active"
    ]
    assert len(matches) == 1
    return matches[0]


def condition_by_id(session, condition_id):
    matches = [
        row
        for row in list_conditions_by_patient(session, JANE_ID)
        if row["id"] == condition_id
    ]
    assert len(matches) == 1
    return matches[0]


def note_with_body(session, body):
    matches = [
        note
        for note in list_notes_by_patient(session, JANE_ID)
        if note["body"] == body
    ]
    assert len(matches) == 1
    return matches[0]


def listed_ids(items):
    assert isinstance(items, list)
    found = []
    for item in items:
        if isinstance(item, dict):
            found.append(str(item["id"]))
        elif hasattr(item, "id"):
            found.append(str(item.id))
        else:
            found.append(str(item))
    return found


def assert_error(body, code):
    assert isinstance(body, dict)
    assert set(body) == {"error"}
    error = body["error"]
    assert isinstance(error, dict)
    assert set(error) == {"code", "message"}
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert error["message"].strip()


def assert_post_approval_call(recording, session):
    assert len(recording.reminder_calls) == 1
    patient_id, trigger, agent_session = recording.reminder_calls[0]
    assert str(patient_id) == JANE_ID
    assert trigger == "post_approval"
    assert agent_session is session


def assert_reminder_review(result, recording, session):
    assert isinstance(result, dict)
    assert set(result) == {"approved", "reminder_review"}
    review = result["reminder_review"]
    assert isinstance(review, dict)
    assert set(review) == {"suggestions", "answer"}
    assert review["answer"] == REMINDER_ANSWER
    follow_up = recording.follow_ups[0]
    assert follow_up["id"] in listed_ids(review["suggestions"])
    stored = get_suggestion(session, follow_up["id"])
    assert stored is not None
    assert stored["status"] == "pending"


def assert_embedded_note(session, body, suggestion_id, embed_calls):
    assert embed_calls == [body]
    note = note_with_body(session, body)
    assert note["patient_id"] == JANE_ID
    assert note["source_suggestion_id"] == suggestion_id
    assert note["embedding"] == EMBEDDING
    assert len(note["embedding"]) == 768
    assert all(type(value) is float for value in note["embedding"])


def assert_suggestion_schema(result):
    assert isinstance(result, dict)
    payload = dict(result)
    if "unconfirmed" not in payload:
        payload["unconfirmed"] = False
    Suggestion.model_validate(payload)


def test_approve_field_update_writes_chart_audits_and_reviews_reminders(
    seeded_db, monkeypatch
):
    session = seeded_db.session
    recording = install_seams(monkeypatch)
    condition = active_hypertension(session)
    suggestion = save_suggestion(session, target_id=condition["id"])
    recording.expect_approved_ids = (suggestion["id"],)
    recording.expect_condition = (condition["id"], "controlled")

    result = invoke(approve_suggestions, [suggestion["id"]], None, session=session)

    assert listed_ids(result["approved"]) == [suggestion["id"]]
    assert_reminder_review(result, recording, session)
    assert get_suggestion(session, suggestion["id"])["status"] == "approved"
    assert condition_by_id(session, condition["id"])["status"] == "controlled"
    audits = list_audit_logs_by_patient(session, JANE_ID)
    assert len(audits) == 1
    assert audits[0]["action"] == "approved"
    assert audits[0]["suggestion_id"] == suggestion["id"]
    assert_post_approval_call(recording, session)


def test_approve_two_suggestions_runs_reminder_agent_once(seeded_db, monkeypatch):
    session = seeded_db.session
    recording = install_seams(monkeypatch)
    condition = active_hypertension(session)
    first = save_suggestion(session, target_id=condition["id"], reason="First update.")
    second = save_suggestion(
        session,
        target_id=condition["id"],
        reason="Second update.",
    )
    recording.expect_approved_ids = (first["id"], second["id"])
    recording.expect_condition = (condition["id"], "controlled")

    result = invoke(
        approve_suggestions,
        [first["id"], second["id"]],
        None,
        session=session,
    )

    assert set(listed_ids(result["approved"])) == {first["id"], second["id"]}
    assert get_suggestion(session, first["id"])["status"] == "approved"
    assert get_suggestion(session, second["id"])["status"] == "approved"
    assert condition_by_id(session, condition["id"])["status"] == "controlled"
    assert_post_approval_call(recording, session)


def test_approve_edited_after_overrides_stored_after(seeded_db, monkeypatch):
    session = seeded_db.session
    recording = install_seams(monkeypatch)
    condition = active_hypertension(session)
    suggestion = save_suggestion(
        session,
        target_id=condition["id"],
        before={"status": "active"},
        after={"status": "controlled"},
    )
    recording.expect_approved_ids = (suggestion["id"],)
    recording.expect_condition = (condition["id"], "resolved")

    result = invoke(
        approve_suggestions,
        [suggestion["id"]],
        {suggestion["id"]: {"after": {"status": "resolved"}}},
        session=session,
    )

    assert suggestion["id"] in listed_ids(result["approved"])
    updated = condition_by_id(session, condition["id"])
    assert updated["status"] == "resolved"
    assert updated["name"] == "Hypertension"
    assert get_suggestion(session, suggestion["id"])["status"] == "approved"
    audits = list_audit_logs_by_patient(session, JANE_ID)
    assert len(audits) == 1
    assert audits[0]["action"] == "approved"
    assert audits[0]["suggestion_id"] == suggestion["id"]
    assert_post_approval_call(recording, session)


def test_approve_edit_outside_allowlist_is_validation_error(seeded_db, monkeypatch):
    session = seeded_db.session
    recording = install_seams(monkeypatch)
    condition = active_hypertension(session)
    suggestion = save_suggestion(session, target_id=condition["id"])
    conditions_before = list_conditions_by_patient(session, JANE_ID)
    notes_before = list_notes_by_patient(session, JANE_ID)

    result = invoke(
        approve_suggestions,
        [suggestion["id"]],
        {suggestion["id"]: {"after": {"secret": "x"}}},
        session=session,
    )

    assert_error(result, "validation_error")
    assert list_conditions_by_patient(session, JANE_ID) == conditions_before
    assert condition_by_id(session, condition["id"])["status"] == "active"
    assert list_notes_by_patient(session, JANE_ID) == notes_before
    stored = get_suggestion(session, suggestion["id"])
    assert stored["status"] == "pending"
    assert stored["after"] == {"status": "controlled"}
    assert list_audit_logs_by_patient(session, JANE_ID) == []
    assert recording.reminder_calls == []


def test_approve_soap_note_stores_embedded_note(seeded_db, monkeypatch):
    session = seeded_db.session
    recording = install_seams(monkeypatch)
    suggestion = save_suggestion(
        session,
        kind="soap_note",
        target_table="notes",
        target_id=None,
        before={},
        after={"body": SOAP_BODY},
        source="chart_agent",
        citations=[],
    )
    recording.expect_approved_ids = (suggestion["id"],)
    recording.expect_note_body = SOAP_BODY

    result = invoke(approve_suggestions, [suggestion["id"]], None, session=session)

    assert suggestion["id"] in listed_ids(result["approved"])
    assert get_suggestion(session, suggestion["id"])["status"] == "approved"
    assert_embedded_note(session, SOAP_BODY, suggestion["id"], recording.embed_calls)
    assert_post_approval_call(recording, session)


def test_approve_plan_item_stores_embedded_note(seeded_db, monkeypatch):
    session = seeded_db.session
    recording = install_seams(monkeypatch)
    suggestion = save_suggestion(
        session,
        kind="plan_item",
        target_table="notes",
        target_id=None,
        before={},
        after={"body": PLAN_TEXT},
        source="research_add_to_plan",
        citations=[],
    )
    recording.expect_approved_ids = (suggestion["id"],)
    recording.expect_note_body = PLAN_TEXT

    result = invoke(approve_suggestions, [suggestion["id"]], None, session=session)

    assert suggestion["id"] in listed_ids(result["approved"])
    assert get_suggestion(session, suggestion["id"])["status"] == "approved"
    assert_embedded_note(session, PLAN_TEXT, suggestion["id"], recording.embed_calls)
    assert_post_approval_call(recording, session)


def test_reject_pending_suggestion_records_reason_and_leaves_chart(
    seeded_db, monkeypatch
):
    session = seeded_db.session
    recording = install_seams(monkeypatch)
    condition = active_hypertension(session)
    suggestion = save_suggestion(session, target_id=condition["id"])
    conditions_before = list_conditions_by_patient(session, JANE_ID)

    result = invoke(
        reject_suggestions,
        [suggestion["id"]],
        REJECT_REASON,
        session=session,
    )

    assert set(result) == {"rejected"}
    assert listed_ids(result["rejected"]) == [suggestion["id"]]
    assert get_suggestion(session, suggestion["id"])["status"] == "rejected"
    audits = list_audit_logs_by_patient(session, JANE_ID)
    assert len(audits) == 1
    assert audits[0]["action"] == "rejected"
    assert audits[0]["detail"] == REJECT_REASON
    assert audits[0]["suggestion_id"] == suggestion["id"]
    assert list_conditions_by_patient(session, JANE_ID) == conditions_before
    assert condition_by_id(session, condition["id"])["status"] == "active"
    assert recording.reminder_calls == []


def test_second_approve_of_approved_suggestion_is_invalid_state(
    seeded_db, monkeypatch
):
    session = seeded_db.session
    recording = install_seams(monkeypatch)
    condition = active_hypertension(session)
    suggestion = save_suggestion(session, target_id=condition["id"])
    recording.expect_approved_ids = (suggestion["id"],)
    recording.expect_condition = (condition["id"], "controlled")

    invoke(approve_suggestions, [suggestion["id"]], None, session=session)
    assert get_suggestion(session, suggestion["id"])["status"] == "approved"
    conditions_after = list_conditions_by_patient(session, JANE_ID)
    notes_after = list_notes_by_patient(session, JANE_ID)
    audits_after = list_audit_logs_by_patient(session, JANE_ID)
    calls_after = list(recording.reminder_calls)

    second = invoke(approve_suggestions, [suggestion["id"]], None, session=session)

    assert_error(second, "invalid_state")
    assert list_conditions_by_patient(session, JANE_ID) == conditions_after
    assert list_notes_by_patient(session, JANE_ID) == notes_after
    assert list_audit_logs_by_patient(session, JANE_ID) == audits_after
    assert recording.reminder_calls == calls_after
    assert get_suggestion(session, suggestion["id"])["status"] == "approved"
    assert condition_by_id(session, condition["id"])["status"] == "controlled"


def test_reject_of_approved_suggestion_is_invalid_state(seeded_db, monkeypatch):
    session = seeded_db.session
    recording = install_seams(monkeypatch)
    condition = active_hypertension(session)
    suggestion = save_suggestion(session, target_id=condition["id"])
    recording.expect_approved_ids = (suggestion["id"],)
    recording.expect_condition = (condition["id"], "controlled")

    invoke(approve_suggestions, [suggestion["id"]], None, session=session)
    assert get_suggestion(session, suggestion["id"])["status"] == "approved"
    conditions_after = list_conditions_by_patient(session, JANE_ID)
    notes_after = list_notes_by_patient(session, JANE_ID)
    audits_after = list_audit_logs_by_patient(session, JANE_ID)
    calls_after = list(recording.reminder_calls)

    second = invoke(
        reject_suggestions,
        [suggestion["id"]],
        REJECT_REASON,
        session=session,
    )

    assert_error(second, "invalid_state")
    assert list_conditions_by_patient(session, JANE_ID) == conditions_after
    assert list_notes_by_patient(session, JANE_ID) == notes_after
    assert list_audit_logs_by_patient(session, JANE_ID) == audits_after
    assert recording.reminder_calls == calls_after
    assert get_suggestion(session, suggestion["id"])["status"] == "approved"
    assert condition_by_id(session, condition["id"])["status"] == "controlled"


def test_list_suggestions_defaults_to_pending_and_filters_approved(seeded_db):
    session = seeded_db.session
    pending = save_suggestion(session, status="pending", reason="Pending change.")
    approved = save_suggestion(session, status="approved", reason="Already approved.")
    rejected = save_suggestion(session, status="rejected", reason="Already rejected.")
    other_patient = save_suggestion(
        session,
        patient_id=AMY_ID,
        status="pending",
        reason="Another patient's pending change.",
    )

    default = invoke(list_suggestions, JANE_ID, None, session=session)

    assert set(default) == {"suggestions"}
    assert isinstance(default["suggestions"], list)
    assert set(listed_ids(default["suggestions"])) == {pending["id"]}
    assert all(item["status"] == "pending" for item in default["suggestions"])
    assert approved["id"] not in listed_ids(default["suggestions"])
    assert rejected["id"] not in listed_ids(default["suggestions"])
    assert other_patient["id"] not in listed_ids(default["suggestions"])

    approved_only = invoke(list_suggestions, JANE_ID, "approved", session=session)

    assert set(approved_only) == {"suggestions"}
    assert set(listed_ids(approved_only["suggestions"])) == {approved["id"]}
    assert all(item["status"] == "approved" for item in approved_only["suggestions"])
    assert pending["id"] not in listed_ids(approved_only["suggestions"])
    assert rejected["id"] not in listed_ids(approved_only["suggestions"])


def test_create_plan_item_returns_pending_suggestion_without_writing_note(
    seeded_db, monkeypatch
):
    session = seeded_db.session
    recording = install_seams(monkeypatch)
    notes_before = list_notes_by_patient(session, JANE_ID)
    citations = [dict(CITATION)]

    result = invoke(
        create_plan_item,
        JANE_ID,
        None,
        PLAN_TEXT,
        citations,
        session=session,
    )

    assert result["patient_id"] == JANE_ID
    assert result["request_id"] is None
    assert result["status"] == "pending"
    assert result["kind"] == "plan_item"
    assert result["source"] == "research_add_to_plan"
    assert result["target_table"] == "notes"
    assert result["after"] == {"body": PLAN_TEXT}
    assert result["citations"] == citations
    assert_suggestion_schema(result)
    stored = get_suggestion(session, result["id"])
    assert stored is not None
    assert stored["status"] == "pending"
    assert stored["kind"] == "plan_item"
    assert stored["source"] == "research_add_to_plan"
    assert stored["target_table"] == "notes"
    assert stored["after"] == {"body": PLAN_TEXT}
    assert stored["citations"] == citations
    assert stored["request_id"] is None
    assert list_notes_by_patient(session, JANE_ID) == notes_before
    assert all(note["body"] != PLAN_TEXT for note in notes_before)
    assert recording.embed_calls == []
    assert recording.reminder_calls == []


def test_approval_source_does_not_reference_mcp():
    source = APPROVAL_SOURCE.read_text(encoding="utf-8")
    assert "app.mcp" not in source
