from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

import app.config as config
import app.services.sms as sms_module
from app.db.repositories import (
    get_patient,
    get_reminder,
    get_sms_message_by_sid,
    insert_reminder,
    insert_sms_message,
    list_conditions_by_patient,
    list_medications_by_patient,
    list_notes_by_patient,
    list_observations_by_patient,
    list_reminder_rules,
    list_reminders_by_patient,
    list_suggestions,
)
from app.services.reminders import send_due_reminders, update_reminder
from app.services.sms import handle_sms_webhook

JANE_ID = "11111111-1111-4111-8111-111111111111"
JOHN_ID = "22222222-2222-4222-8222-222222222222"
AMY_ID = "33333333-3333-4333-8333-333333333333"

JANE_PHONE = "+15555550101"
JOHN_PHONE = "+15555550102"
AMY_PHONE = "+15555550103"

TWILIO_FROM = "whatsapp:+15550001111"
PATIENT_IDS = (JANE_ID, JOHN_ID, AMY_ID)

JANE_FORBIDDEN = ("Hypertension", "Lisinopril", "LDL", "140")
JOHN_FORBIDDEN = ("COPD", "Tiotropium", "SpO2")
AMY_FORBIDDEN = ("Diverticulosis", "Psyllium", "Hemoglobin")


def invoke(fn, *args, session, **kwargs):
    import inspect

    if "session" in inspect.signature(fn).parameters:
        kwargs["session"] = session
    return fn(*args, **kwargs)


def whatsapp(phone_e164):
    return "whatsapp:" + phone_e164


def install_whatsapp(monkeypatch):
    calls = []

    def send_whatsapp(from_number, to, body):
        calls.append((from_number, to, body))
        return "SM" + str(len(calls))

    monkeypatch.setattr(sms_module, "send_whatsapp", send_whatsapp, raising=False)
    monkeypatch.setattr(config, "TWILIO_FROM_NUMBER", TWILIO_FROM, raising=False)
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
        assert set(item) == {"reminder_id", "sms_id"}
        assert isinstance(item["reminder_id"], str)
        assert isinstance(item["sms_id"], str)
        assert item["reminder_id"] not in sent_ids
        sent_ids[item["reminder_id"]] = item["sms_id"]
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


def assert_sent(session, calls, reminder, phone_e164, forbidden, sms_id):
    to = whatsapp(phone_e164)
    matched = [index for index, call in enumerate(calls) if call[1] == to]
    assert len(matched) == 1
    index = matched[0]
    from_number, to_number, body = calls[index]
    assert from_number == TWILIO_FROM
    assert to_number == to
    assert_hides_chart(body, forbidden)
    sid = "SM" + str(index + 1)
    row = get_sms_message_by_sid(session, sid)
    assert row["twilio_sid"] == sid
    assert row["to_phone"] == to
    assert row["body"] == body
    assert row["id"] == sms_id
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


def assert_no_call(calls, phone_e164):
    banned = whatsapp(phone_e164)
    assert all(call[1] != banned for call in calls)


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
    calls = install_whatsapp(monkeypatch)

    result = invoke(send_due_reminders, date(2026, 9, 15), session=session)

    sent_ids, skipped_ids = partition(result)
    assert set(sent_ids) == {amy["id"]}
    assert skipped_ids == {}
    assert_absent(jane["id"], sent_ids, skipped_ids)
    assert_absent(john["id"], sent_ids, skipped_ids)
    assert len(calls) == 1
    assert_sent(session, calls, amy, AMY_PHONE, AMY_FORBIDDEN, sent_ids[amy["id"]])
    assert_still_scheduled(session, jane)
    assert_still_scheduled(session, john)
    assert_no_call(calls, JANE_PHONE)
    assert_no_call(calls, JOHN_PHONE)


def test_as_of_november_sends_jane_and_amy_and_skips_john(seeded_db, monkeypatch):
    session = seeded_db.session
    jane, john, amy = seeded_reminders(session)
    calls = install_whatsapp(monkeypatch)

    result = invoke(send_due_reminders, date(2026, 11, 1), session=session)

    sent_ids, skipped_ids = partition(result)
    assert set(sent_ids) == {jane["id"], amy["id"]}
    assert skipped_ids == {john["id"]: "opted_out"}
    assert len(calls) == 2
    assert_sent(session, calls, jane, JANE_PHONE, JANE_FORBIDDEN, sent_ids[jane["id"]])
    assert_sent(session, calls, amy, AMY_PHONE, AMY_FORBIDDEN, sent_ids[amy["id"]])
    assert_still_scheduled(session, john)
    assert_no_call(calls, JOHN_PHONE)


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
    calls = install_whatsapp(monkeypatch)

    result = invoke(send_due_reminders, date(2026, 11, 1), session=session)

    sent_ids, skipped_ids = partition(result)
    assert_absent(paused_id, sent_ids, skipped_ids)
    assert set(sent_ids) == {jane["id"], amy["id"]}
    assert skipped_ids == {john["id"]: "opted_out"}
    stored = get_reminder(session, paused_id)
    assert stored["status"] == "paused"
    assert stored["due_on"] == date(2026, 1, 1)
    assert stored["name"] == "Paused screening"
    assert_sent(session, calls, jane, JANE_PHONE, JANE_FORBIDDEN, sent_ids[jane["id"]])
    assert_sent(session, calls, amy, AMY_PHONE, AMY_FORBIDDEN, sent_ids[amy["id"]])
    assert_no_call(calls, JOHN_PHONE)
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


@pytest.mark.parametrize(
    "body",
    [" STOP ", "stop", "Stop"],
    ids=["spaced", "lower", "capitalized"],
)
def test_stop_opts_jane_out_without_changing_the_chart(seeded_db, body):
    session = seeded_db.session
    before = snapshot_charts(session)

    result = invoke(
        handle_sms_webhook,
        {
            "MessageSid": "SMstop",
            "MessageStatus": "received",
            "From": whatsapp(JANE_PHONE),
            "Body": body,
        },
        session=session,
    )

    assert result is None
    jane = get_patient(session, JANE_ID)
    assert jane["sms_opt_in"] is False
    assert jane["phone_e164"] == JANE_PHONE
    assert jane["display_name"] == "Jane Doe"
    assert get_patient(session, JOHN_ID)["sms_opt_in"] is False
    assert get_patient(session, AMY_ID)["sms_opt_in"] is True
    assert snapshot_charts(session) == before


def test_delivery_status_updates_sms_message(seeded_db):
    session = seeded_db.session
    jane = reminder_named(session, JANE_ID, "Colorectal cancer screening")
    sms_id = str(uuid4())
    insert_sms_message(
        session,
        {
            "id": sms_id,
            "patient_id": JANE_ID,
            "reminder_id": jane["id"],
            "to_phone": whatsapp(JANE_PHONE),
            "body": "Clinic reminder",
            "twilio_sid": "SM999",
            "status": "queued",
        },
    )
    before_sms = get_sms_message_by_sid(session, "SM999")
    assert before_sms["status"] == "queued"
    before = snapshot_charts(session)

    result = invoke(
        handle_sms_webhook,
        {
            "MessageSid": "SM999",
            "MessageStatus": "delivered",
            "From": whatsapp(JANE_PHONE),
            "Body": "ok",
        },
        session=session,
    )

    assert result is None
    after_sms = get_sms_message_by_sid(session, "SM999")
    assert after_sms["status"] == "delivered"
    assert after_sms["id"] == sms_id
    assert after_sms["twilio_sid"] == "SM999"
    assert after_sms["to_phone"] == whatsapp(JANE_PHONE)
    assert after_sms["body"] == "Clinic reminder"
    assert after_sms["patient_id"] == JANE_ID
    assert after_sms["reminder_id"] == jane["id"]
    assert {**after_sms, "status": "queued"} == before_sms
    assert snapshot_charts(session) == before
    assert get_patient(session, JANE_ID)["sms_opt_in"] is True


def test_unknown_webhook_returns_none(seeded_db):
    session = seeded_db.session
    before = snapshot_charts(session)
    opt_in = {
        patient_id: get_patient(session, patient_id)["sms_opt_in"]
        for patient_id in PATIENT_IDS
    }

    result = invoke(
        handle_sms_webhook,
        {
            "MessageSid": "SMunknown",
            "MessageStatus": "delivered",
            "From": "whatsapp:+19999999999",
            "Body": "hello",
        },
        session=session,
    )

    assert result is None
    assert snapshot_charts(session) == before
    for patient_id, opted_in in opt_in.items():
        assert get_patient(session, patient_id)["sms_opt_in"] is opted_in


def test_reminder_services_do_not_reference_agents():
    services = Path(__file__).resolve().parents[2] / "app" / "services"
    for name in ("reminders.py", "sms.py"):
        path = services / name
        assert path.is_file()
        assert "app.agents" not in path.read_text(encoding="utf-8")
