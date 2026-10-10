from app.agents.doctor import run_reminder_agent

from support import (
    DEPARTURE_REASON,
    JANE_ID,
    assert_deidentified_evidence,
    assert_model_leaked_tool_text,
    assert_rules,
    baseline_citation,
    condition_status,
    evidence_tool_calls,
    find_unconfirmed,
    insert_pending_chart_suggestion,
    install,
    invoke,
    jane_hypertension,
    literature_citation,
    payloads,
    pending_ids,
    reminder_change,
    reminder_snapshot,
    DoctorModel,
)


def test_post_approval_up_to_date_proposes_nothing_on_a_second_run(seeded_db, monkeypatch):
    session = seeded_db.session
    pending = insert_pending_chart_suggestion(session)
    before_ids = pending_ids(session)
    before_status = condition_status(session)
    before_reminders = reminder_snapshot(session)
    model = DoctorModel(
        reminders={
            "up_to_date": True,
            "answer": "Screenings are up to date.",
            "suggestions": [],
            "tool_calls": [],
        }
    )
    harness = install(monkeypatch, model)

    first = invoke(run_reminder_agent, JANE_ID, "post_approval", session=session)

    assert set(first) == {"suggestions", "answer"}
    assert first["suggestions"] == []
    assert isinstance(first["answer"], str)
    assert "up to date" in first["answer"].lower()
    assert harness.propose_calls == []

    second = invoke(run_reminder_agent, JANE_ID, "post_approval", session=session)

    assert set(second) == {"suggestions", "answer"}
    assert second["suggestions"] == []
    assert isinstance(second["answer"], str)
    assert "up to date" in second["answer"].lower()
    assert harness.propose_calls == []
    assert pending_ids(session) == before_ids
    assert condition_status(session) == before_status
    assert jane_hypertension(session)["status"] == "active"
    assert reminder_snapshot(session) == before_reminders
    reminder_payloads = payloads(model, "reminders")
    assert len(reminder_payloads) >= 2
    assert "classify" not in {task for task, _payload in model.calls}
    for payload in reminder_payloads:
        assert payload["trigger"] == "post_approval"
        assert_rules(payload)
        found = find_unconfirmed(payload["context"], pending["id"])
        assert found is not None
        assert found["unconfirmed"] is True


def test_reminder_change_without_baseline_is_not_proposed(seeded_db, monkeypatch):
    session = seeded_db.session
    citations = [baseline_citation(), literature_citation()]
    before_ids = pending_ids(session)
    before_status = condition_status(session)
    before_reminders = reminder_snapshot(session)

    def verify(payload):
        assert payload["text"] == DEPARTURE_REASON
        assert payload["citations"] == citations
        return {
            "supported": [
                {
                    "sentence": "A paper describes family history.",
                    "citation_indexes": [1],
                }
            ],
            "removed": ["USPSTF baseline: start at 45 for average risk."],
        }

    model = DoctorModel(
        reminders={
            "up_to_date": False,
            "answer": None,
            "suggestions": [reminder_change(citations)],
            "tool_calls": evidence_tool_calls(),
        },
        verify=verify,
    )
    harness = install(monkeypatch, model)

    result = invoke(run_reminder_agent, JANE_ID, "doctor_request", session=session)

    assert set(result) == {"suggestions", "answer"}
    assert result["suggestions"] == []
    assert harness.propose_calls == []
    assert pending_ids(session) == before_ids
    assert condition_status(session) == before_status
    assert reminder_snapshot(session) == before_reminders
    reminder_payload = payloads(model, "reminders")[0]
    assert reminder_payload["trigger"] == "doctor_request"
    assert_rules(reminder_payload)
    assert_model_leaked_tool_text(reminder_payload)
    assert payloads(model, "verify")
    assert_deidentified_evidence(harness.evidence_calls)
