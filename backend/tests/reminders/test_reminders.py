from datetime import date
from pathlib import Path
from uuid import uuid4

import app.config as config
import app.services.email as email_module
from app.db.repositories import (
    get_patient,
    get_reminder,
    get_email_message_by_provider_id,
    insert_reminder,
    list_conditions_by_patient,
    list_medications_by_patient,
    list_notes_by_patient,
    list_observations_by_patient,
    list_reminder_rules,
    list_reminders_by_patient,
    list_suggestions,
)
from app.services.email import unsubscribe
from app.services.reminders import send_due_reminders, update_reminder

JANE_ID = "11111111-1111-4111-8111-111111111111"
JOHN_ID = "22222222-2222-4222-8222-222222222222"
AMY_ID = "33333333-3333-4333-8333-333333333333"

JANE_EMAIL = "jane.doe@example.com"
JOHN_EMAIL = "john.roe@example.com"
AMY_EMAIL = "amy.lee@example.com"

PUBLIC_BASE = "https://clinic.example"
UNSUBSCRIBE_SECRET = "unsubscribe-secret"
PATIENT_IDS = (JANE_ID, JOHN_ID, AMY_ID)

JANE_FORBIDDEN = ("Hypertension", "Lisinopril", "LDL", "140")
JOHN_FORBIDDEN = ("COPD", "Tiotropium", "SpO2")
AMY_FORBIDDEN = ("Diverticulosis", "Psyllium", "Hemoglobin")


def invoke(fn, *args, session, **kwargs):
    import inspect

    if "session" in inspect.signature(fn).parameters:
        kwargs["session"] = session
    return fn(*args, **kwargs)


def install_email(monkeypatch):
    calls = []

    def send_email(to_email, variables):
        calls.append((to_email, variables))
        return "re_" + str(len(calls))

    monkeypatch.setattr(email_module, "send_email", send_email, raising=False)
    monkeypatch.setattr(config, "EMAIL_PUBLIC_BASE_URL", PUBLIC_BASE, raising=False)
    monkeypatch.setattr(config, "EMAIL_UNSUBSCRIBE_SECRET", UNSUBSCRIBE_SECRET, raising=False)
    return calls


def reminder_named(session, patient_id, name):
    rows = list_reminders_by_patient(session, patient_id)
    matches = [row for row in rows if row["name"] == name]
    assert len(matches) == 1
    reminder = matches[0]
    assert isinstance(reminder["id"], str)
    return reminder


def rows_by_id(rows):
    assert isinstance(rows, list)
    indexed = {}
    for row in rows:
        assert isinstance(row, dict)
        indexed[row["id"]] = row
    assert len(indexed) == len(rows)
    return indexed


def chart_snapshot(session, patient_id):
    return {
        "conditions": rows_by_id(list_conditions_by_patient(session, patient_id)),
        "medications": rows_by_id(list_medications_by_patient(session, patient_id)),
        "observations": rows_by_id(list_observations_by_patient(session, patient_id)),
        "notes": rows_by_id(list_notes_by_patient(session, patient_id)),
        "reminders": rows_by_id(list_reminders_by_patient(session, patient_id)),
    }


def snapshot_charts(session):
    return {patient_id: chart_snapshot(session, patient_id) for patient_id in PATIENT_IDS}


def assert_hides_chart(body, forbidden):
    assert isinstance(body, str)
    folded = body.casefold()
    for term in forbidden:
        assert term.casefold() not in folded


def partition(result):
    assert isinstance(result, dict)
    assert set(result) == {"sent", "skipped"}
    sent = result["sent"]
    skipped = result["skipped"]
    assert isinstance(sent, list)
    assert isinstance(skipped, list)
    sent_ids = {}
    for item in sent:
        assert set(item) == {"reminder_id", "email_id"}
        assert isinstance(item["reminder_id"], str)
        assert isinstance(item["email_id"], str)
        assert item["reminder_id"] not in sent_ids
        sent_ids[item["reminder_id"]] = item["email_id"]
    skipped_ids = {}
    for item in skipped:
        assert set(item) == {"reminder_id", "reason"}
        assert isinstance(item["reminder_id"], str)
        assert isinstance(item["reason"], str)
        assert item["reminder_id"] not in skipped_ids
        skipped_ids[item["reminder_id"]] = item["reason"]
    assert sent_ids.keys().isdisjoint(skipped_ids)
    return sent_ids, skipped_ids


def assert_absent(reminder_id, sent_ids, skipped_ids):
    assert reminder_id not in sent_ids
    assert reminder_id not in skipped_ids


def assert_sent(session, calls, reminder, address, forbidden, email_id):
    matched = [index for index, call in enumerate(calls) if call[0] == address]
    assert len(matched) == 1
    index = matched[0]
    to_email, variables = calls[index]
    assert to_email == address
    patient = get_patient(session, reminder["patient_id"])
    link = email_module.unsubscribe_link(reminder["patient_id"])
    assert variables == email_module.template_variables(
        patient["display_name"], reminder["name"], reminder["due_on"], link
    )
    body = email_module.reminder_text(
        patient["display_name"], reminder["name"], reminder["due_on"], link
    )
    assert link.startswith(PUBLIC_BASE + "/email/unsubscribe?token=")
    assert_hides_chart(body, forbidden)
    provider_id = "re_" + str(index + 1)
    row = get_email_message_by_provider_id(session, provider_id)
    assert row["provider_id"] == provider_id
    assert row["to_email"] == address
    assert row["body"] == body
    assert row["status"] == "sent"
    assert row["id"] == email_id
    assert isinstance(row["id"], str)
    assert row["patient_id"] == reminder["patient_id"]
    assert row["reminder_id"] == reminder["id"]
    stored = get_reminder(session, reminder["id"])
    assert stored["status"] == "sent"
    assert stored["id"] == reminder["id"]
    assert stored["patient_id"] == reminder["patient_id"]
    assert stored["rule_id"] == reminder["rule_id"]
    assert stored["name"] == reminder["name"]
    assert stored["due_on"] == reminder["due_on"]


def assert_still_scheduled(session, reminder):
    stored = get_reminder(session, reminder["id"])
    assert stored["status"] == "scheduled"
    assert stored["due_on"] == reminder["due_on"]
    assert stored["name"] == reminder["name"]
    assert stored["patient_id"] == reminder["patient_id"]
    assert stored["rule_id"] == reminder["rule_id"]


def assert_no_call(calls, address):
    assert all(call[0] != address for call in calls)


def assert_error(result, code):
    assert isinstance(result, dict)
    assert set(result) == {"error"}
    error = result["error"]
    assert isinstance(error, dict)
    assert set(error) == {"code", "message"}
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert error["message"]


def seeded_reminders(session):
    return (
        reminder_named(session, JANE_ID, "Colorectal cancer screening"),
        reminder_named(session, JOHN_ID, "Lung cancer screening"),
        reminder_named(session, AMY_ID, "Follow-up labs"),
    )


def test_as_of_mid_september_sends_only_amy(seeded_db, monkeypatch):
    session = seeded_db.session
    jane, john, amy = seeded_reminders(session)
    calls = install_email(monkeypatch)

    result = invoke(send_due_reminders, date(2026, 9, 15), session=session)

    sent_ids, skipped_ids = partition(result)
    assert set(sent_ids) == {amy["id"]}
    assert skipped_ids == {}
    assert_absent(jane["id"], sent_ids, skipped_ids)
    assert_absent(john["id"], sent_ids, skipped_ids)
    assert len(calls) == 1
    assert_sent(session, calls, amy, AMY_EMAIL, AMY_FORBIDDEN, sent_ids[amy["id"]])
    assert_still_scheduled(session, jane)
    assert_still_scheduled(session, john)
    assert_no_call(calls, JANE_EMAIL)
    assert_no_call(calls, JOHN_EMAIL)


def test_as_of_november_sends_jane_and_amy_and_skips_john(seeded_db, monkeypatch):
    session = seeded_db.session
    jane, john, amy = seeded_reminders(session)
    calls = install_email(monkeypatch)

    result = invoke(send_due_reminders, date(2026, 11, 1), session=session)

    sent_ids, skipped_ids = partition(result)
    assert set(sent_ids) == {jane["id"], amy["id"]}
    assert skipped_ids == {john["id"]: "opted_out"}
    assert len(calls) == 2
    assert_sent(session, calls, jane, JANE_EMAIL, JANE_FORBIDDEN, sent_ids[jane["id"]])
    assert_sent(session, calls, amy, AMY_EMAIL, AMY_FORBIDDEN, sent_ids[amy["id"]])
    assert_still_scheduled(session, john)
    assert_no_call(calls, JOHN_EMAIL)


def test_paused_due_reminder_is_neither_sent_nor_skipped(seeded_db, monkeypatch):
    session = seeded_db.session
    jane, john, amy = seeded_reminders(session)
    paused_id = str(uuid4())
    insert_reminder(
        session,
        {
            "id": paused_id,
            "patient_id": JANE_ID,
            "rule_id": list_reminder_rules(session)[0]["id"],
            "name": "Paused screening",
            "due_on": date(2026, 1, 1),
            "status": "paused",
        },
    )
    paused = get_reminder(session, paused_id)
    assert paused["status"] == "paused"
    assert paused["due_on"] == date(2026, 1, 1)
    calls = install_email(monkeypatch)

    result = invoke(send_due_reminders, date(2026, 11, 1), session=session)

    sent_ids, skipped_ids = partition(result)
    assert_absent(paused_id, sent_ids, skipped_ids)
    assert set(sent_ids) == {jane["id"], amy["id"]}
    assert skipped_ids == {john["id"]: "opted_out"}
    stored = get_reminder(session, paused_id)
    assert stored["status"] == "paused"
    assert stored["due_on"] == date(2026, 1, 1)
    assert stored["name"] == "Paused screening"
    assert_sent(session, calls, jane, JANE_EMAIL, JANE_FORBIDDEN, sent_ids[jane["id"]])
    assert_sent(session, calls, amy, AMY_EMAIL, AMY_FORBIDDEN, sent_ids[amy["id"]])
    assert_no_call(calls, JOHN_EMAIL)
    assert len(calls) == 2


def test_update_reminder_changes_only_due_on_and_status(seeded_db):
    session = seeded_db.session
    jane = reminder_named(session, JANE_ID, "Colorectal cancer screening")

    result = invoke(
        update_reminder,
        JANE_ID,
        jane["id"],
        date(2026, 12, 1),
        "paused",
        session=session,
    )

    assert set(result) == {"id", "patient_id", "name", "due_on", "status"}
    assert result["id"] == jane["id"]
    assert isinstance(result["id"], str)
    assert result["patient_id"] == JANE_ID
    assert result["name"] == "Colorectal cancer screening"
    assert result["due_on"] == "2026-12-01"
    assert result["status"] == "paused"
    stored = get_reminder(session, jane["id"])
    assert stored["id"] == jane["id"]
    assert stored["patient_id"] == JANE_ID
    assert stored["rule_id"] == jane["rule_id"]
    assert stored["name"] == jane["name"]
    assert stored["due_on"] == date(2026, 12, 1)
    assert stored["status"] == "paused"
    assert list_suggestions(session, JANE_ID) == []


def test_update_reminder_rejects_unknown_status(seeded_db):
    session = seeded_db.session
    jane = reminder_named(session, JANE_ID, "Colorectal cancer screening")
    invoke(
        update_reminder,
        JANE_ID,
        jane["id"],
        date(2026, 12, 1),
        "paused",
        session=session,
    )

    result = invoke(
        update_reminder,
        JANE_ID,
        jane["id"],
        date(2027, 5, 1),
        "nope",
        session=session,
    )

    assert_error(result, "validation_error")
    stored = get_reminder(session, jane["id"])
    assert stored["status"] == "paused"
    assert stored["due_on"] == date(2026, 12, 1)
    assert stored["name"] == jane["name"]
    assert stored["rule_id"] == jane["rule_id"]


def test_update_reminder_unknown_id_is_not_found(seeded_db):
    session = seeded_db.session
    jane = reminder_named(session, JANE_ID, "Colorectal cancer screening")
    missing_id = str(uuid4())

    result = invoke(
        update_reminder,
        JANE_ID,
        missing_id,
        date(2026, 12, 1),
        "paused",
        session=session,
    )

    assert_error(result, "not_found")
    stored = get_reminder(session, jane["id"])
    assert stored["status"] == "scheduled"
    assert stored["due_on"] == date(2026, 10, 1)
    assert stored["name"] == jane["name"]
    assert stored["patient_id"] == JANE_ID


def test_update_reminder_for_other_patient_is_not_found(seeded_db):
    session = seeded_db.session
    jane = reminder_named(session, JANE_ID, "Colorectal cancer screening")

    result = invoke(
        update_reminder,
        JOHN_ID,
        jane["id"],
        date(2027, 1, 1),
        "done",
        session=session,
    )

    assert_error(result, "not_found")
    stored = get_reminder(session, jane["id"])
    assert stored["status"] == jane["status"]
    assert stored["due_on"] == jane["due_on"]
    assert stored["name"] == jane["name"]
    assert stored["patient_id"] == JANE_ID
    assert stored["rule_id"] == jane["rule_id"]


def test_update_reminder_without_due_on_updates_status_only(seeded_db):
    session = seeded_db.session
    jane = reminder_named(session, JANE_ID, "Colorectal cancer screening")

    result = invoke(
        update_reminder,
        JANE_ID,
        jane["id"],
        None,
        "done",
        session=session,
    )

    assert set(result) == {"id", "patient_id", "name", "due_on", "status"}
    assert result["id"] == jane["id"]
    assert result["patient_id"] == JANE_ID
    assert result["name"] == jane["name"]
    assert result["due_on"] == "2026-10-01"
    assert result["status"] == "done"
    stored = get_reminder(session, jane["id"])
    assert stored["status"] == "done"
    assert stored["due_on"] == date(2026, 10, 1)
    assert stored["name"] == jane["name"]
    assert stored["rule_id"] == jane["rule_id"]
    assert stored["patient_id"] == JANE_ID


def test_unsubscribe_opts_jane_out_without_changing_the_chart(seeded_db, monkeypatch):
    session = seeded_db.session
    install_email(monkeypatch)
    before = snapshot_charts(session)
    token = email_module.unsubscribe_token(JANE_ID)

    result = invoke(unsubscribe, token, session=session)

    assert result == "You are unsubscribed from clinic reminders."
    jane = get_patient(session, JANE_ID)
    assert jane["email_opt_in"] is False
    assert jane["email"] == JANE_EMAIL
    assert jane["display_name"] == "Jane Doe"
    assert get_patient(session, JOHN_ID)["email_opt_in"] is False
    assert get_patient(session, AMY_ID)["email_opt_in"] is True
    assert snapshot_charts(session) == before


def test_unsubscribe_again_stays_opted_out(seeded_db, monkeypatch):
    session = seeded_db.session
    install_email(monkeypatch)
    token = email_module.unsubscribe_token(JANE_ID)
    invoke(unsubscribe, token, session=session)
    before = snapshot_charts(session)

    result = invoke(unsubscribe, token, session=session)

    assert result == "You are unsubscribed from clinic reminders."
    jane = get_patient(session, JANE_ID)
    assert jane["email_opt_in"] is False
    assert jane["email"] == JANE_EMAIL
    assert snapshot_charts(session) == before


def test_bad_unsubscribe_token_changes_nothing(seeded_db, monkeypatch):
    session = seeded_db.session
    install_email(monkeypatch)
    before = snapshot_charts(session)
    opt_in = {
        patient_id: get_patient(session, patient_id)["email_opt_in"]
        for patient_id in PATIENT_IDS
    }

    result = invoke(unsubscribe, JANE_ID + ".not-a-valid-signature", session=session)
    signed_garbage = invoke(
        unsubscribe,
        email_module.unsubscribe_token("not-a-patient"),
        session=session,
    )

    assert result is None
    assert signed_garbage is None
    assert snapshot_charts(session) == before
    for patient_id, opted_in in opt_in.items():
        assert get_patient(session, patient_id)["email_opt_in"] is opted_in
        assert get_patient(session, patient_id)["email"] == {
            JANE_ID: JANE_EMAIL,
            JOHN_ID: JOHN_EMAIL,
            AMY_ID: AMY_EMAIL,
        }[patient_id]


def test_failed_send_leaves_the_reminder_scheduled(seeded_db, monkeypatch):
    session = seeded_db.session
    amy = reminder_named(session, AMY_ID, "Follow-up labs")

    def send_email(to_email, variables):
        raise RuntimeError("resend rejected the message")

    monkeypatch.setattr(email_module, "send_email", send_email, raising=False)
    monkeypatch.setattr(config, "EMAIL_PUBLIC_BASE_URL", PUBLIC_BASE, raising=False)
    monkeypatch.setattr(config, "EMAIL_UNSUBSCRIBE_SECRET", UNSUBSCRIBE_SECRET, raising=False)

    try:
        invoke(send_due_reminders, date(2026, 9, 15), session=session)
    except RuntimeError as exc:
        assert str(exc) == "resend rejected the message"
    else:
        raise AssertionError("send_due_reminders swallowed the failed send")

    assert_still_scheduled(session, amy)
    assert get_email_message_by_provider_id(session, "re_1") is None


def test_send_email_posts_to_resend_and_returns_the_message_id(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "re_abc"}

    def post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(config, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(config, "EMAIL_FROM", "Clinic <reminders@example.com>")
    monkeypatch.setattr(config, "EMAIL_TEMPLATE_ID", "clinic-reminder")
    monkeypatch.setattr(email_module.httpx, "post", post)
    variables = {
        "PATIENT_NAME": "Jane Doe",
        "REMINDER_NAME": "Follow-up labs",
        "DUE_ON": "September 1, 2026",
        "UNSUBSCRIBE_URL": "https://clinic.example/email/unsubscribe?token=abc",
    }

    message_id = email_module.send_email("jane.doe@example.com", variables)

    assert message_id == "re_abc"
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer re_test"
    assert captured["json"] == {
        "from": "Clinic <reminders@example.com>",
        "to": ["jane.doe@example.com"],
        "template": {"id": "clinic-reminder", "variables": variables},
    }


def test_reminder_services_do_not_reference_agents():
    services = Path(__file__).resolve().parents[2] / "app" / "services"
    for name in ("reminders.py", "email.py"):
        path = services / name
        assert path.is_file()
        assert "app.agents" not in path.read_text(encoding="utf-8")
