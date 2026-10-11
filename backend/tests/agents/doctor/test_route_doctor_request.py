from app.agents.doctor import route_doctor_request
import pytest

from support import (
    DEPARTURE_REASON,
    JANE_ID,
    assert_context_call,
    assert_departure_reason,
    assert_deidentified_evidence,
    assert_model_leaked_tool_text,
    assert_new_pending,
    assert_proposed,
    assert_request,
    assert_rules,
    assert_typed_silent,
    baseline_citation,
    chart_citation,
    citation_tiers,
    condition_status,
    evidence_tool_calls,
    field_update,
    find_unconfirmed,
    guideline_citation,
    insert_pending_chart_suggestion,
    install,
    invoke,
    jane_hypertension,
    jane_note,
    jane_screening,
    literature_citation,
    payloads,
    pending_ids,
    reminder_change,
    reminder_snapshot,
    DoctorModel,
)


@pytest.mark.parametrize("route", ["clinical_question", "chart_update", "check_screenings"])
def test_explicit_workflow_skips_classifier(seeded_db, monkeypatch, route):
    model = DoctorModel(route="chart_update", chart={"suggestions": []}, research={"answer": {"text": "Recorded finding.", "citations": [baseline_citation()]}, "recommends_action": False}, reminders={"up_to_date": True, "answer": "No change.", "suggestions": []})
    install(monkeypatch, model)
    result = route_doctor_request(JANE_ID, "Clinical question", "typed", session=seeded_db.session, route=route)
    assert result["route"] == route
    assert not payloads(model, "classify")


def test_research_sections_drop_unsupported_claims_and_keep_source_links(seeded_db, monkeypatch):
    citation = baseline_citation()
    def verify(payload):
        return {"supported": [{"sentence": payload["text"], "citation_indexes": [0]}] if payload["text"] == "Supported finding." else [], "removed": []}
    model = DoctorModel(research={"answer": {"text": "Unused duplicate text.", "citations": [citation], "sections": [{"title": "Clinical interpretation", "text": "Supported finding."}, {"title": "Opposing findings", "text": "Unsupported possibility."}]}, "recommends_action": False}, verify=verify)
    install(monkeypatch, model)
    result = route_doctor_request(JANE_ID, "What explains these findings?", "typed", session=seeded_db.session, route="clinical_question")
    assert result["suggestions"] == []
    assert result["answer"]["text"] == "Supported finding."
    assert result["answer"]["sections"] == [{"title": "Clinical interpretation", "text": "Supported finding.", "source_ids": [citation["source_id"]]}]
    assert result["answer"]["citations"] == [citation]


def test_general_research_never_loads_a_patient_chart(monkeypatch):
    from app.agents.doctor import _research_answer
    citation = baseline_citation()
    model = DoctorModel(research={"answer": {"text": "General clinical evidence.", "citations": [citation]}, "tool_calls": [{"name": "search_patient_notes", "query": "patient history"}], "recommends_action": False})
    harness = install(monkeypatch, model)
    result = _research_answer(None, "General clinical question", None)
    assert result["text"] == "General clinical evidence."
    payload = payloads(model, "research")[0]
    assert payload["context"] == {}
    assert payload["notes"] == {}
    assert payload["tool_calls"] == []
    assert harness.context_calls == []
    assert harness.propose_calls == []


def test_typed_chart_update_proposes_without_writing_the_chart(seeded_db, monkeypatch):
    session = seeded_db.session
    text = "Mark hypertension controlled."
    note = jane_note(session)
    condition = jane_hypertension(session)
    pending = insert_pending_chart_suggestion(session)
    before_ids = pending_ids(session)
    before_status = condition_status(session)
    suggestion = field_update([chart_citation(note)], condition["id"])
    model = DoctorModel(
        route="chart_update",
        chart={"suggestions": [suggestion]},
    )
    harness = install(monkeypatch, model)

    result = invoke(route_doctor_request, JANE_ID, text, "typed", session=session)

    assert_request(session, result, text=text, channel="typed", route="chart_update")
    assert_typed_silent(result)
    assert result["answer"] is None
    assert_new_pending(session, before_ids, result["suggestions"])
    assert pending["id"] not in {item["id"] for item in result["suggestions"]}
    stored = result["suggestions"][0]
    assert stored["kind"] == "field_update"
    assert stored["source"] == "chart_agent"
    assert stored["target_table"] == "conditions"
    assert stored["after"] == {"status": "controlled"}
    assert any(
        item["tier"] == "chart"
        and (
            item["locator"].startswith("note:")
            or item["locator"].startswith("observation:")
        )
        for item in stored["citations"]
    )
    assert condition_status(session) == before_status
    assert jane_hypertension(session)["status"] == "active"
    assert model.calls[0] == ("classify", {"text": text})
    chart_payload = payloads(model, "chart")[0]
    assert chart_payload["text"] == text
    assert isinstance(chart_payload["context"], dict)
    found = find_unconfirmed(chart_payload["context"], pending["id"])
    assert found is not None
    assert found["unconfirmed"] is True
    assert_context_call(harness)
    assert_proposed(harness, "field_update")
    assert harness.evidence_calls == []
    assert "research" not in {task for task, _payload in model.calls}
    assert "reminders" not in {task for task, _payload in model.calls}


def test_voice_chart_update_returns_spoken_text_without_audio(seeded_db, monkeypatch):
    session = seeded_db.session
    text = "Mark hypertension controlled."
    note = jane_note(session)
    condition = jane_hypertension(session)
    before_ids = pending_ids(session)
    before_status = condition_status(session)
    model = DoctorModel(
        route="chart_update",
        chart={"suggestions": [field_update([chart_citation(note)], condition["id"])]},
    )
    harness = install(monkeypatch, model)

    result = invoke(route_doctor_request, JANE_ID, text, "voice", session=session)

    assert_request(session, result, text=text, channel="voice", route="chart_update")
    assert isinstance(result["spoken_text"], str)
    assert result["spoken_text"].strip()
    assert result["audio_base64"] is None
    assert result["answer"] is None
    assert_new_pending(session, before_ids, result["suggestions"])
    assert all(item["status"] == "pending" for item in result["suggestions"])
    assert condition_status(session) == before_status
    assert_context_call(harness)
    assert_proposed(harness, "field_update")
    assert harness.evidence_calls == []


def test_clinical_question_keeps_baseline_guideline_and_chart(seeded_db, monkeypatch):
    session = seeded_db.session
    text = "When should colorectal screening start?"
    note = jane_note(session)
    baseline = baseline_citation()
    guideline = guideline_citation()
    chart = chart_citation(note)
    citations = [baseline, guideline, chart]
    supported = [
        {
            "sentence": "USPSTF baseline screening starts at 45.",
            "citation_indexes": [0],
        },
        {
            "sentence": "A specialty guideline supports earlier screening.",
            "citation_indexes": [1],
        },
        {
            "sentence": "The chart records this patient's history.",
            "citation_indexes": [2],
        },
    ]
    expected_text = " ".join(item["sentence"] for item in supported)
    answer_text = f"{expected_text} An extra claim is not supported."

    def verify(payload):
        assert payload["text"] == answer_text
        assert payload["citations"] == citations
        return {"supported": supported, "removed": ["An extra claim is not supported."]}

    model = DoctorModel(
        route="clinical_question",
        research={
            "tool_calls": evidence_tool_calls(include_notes=True),
            "answer": {"text": answer_text, "citations": citations},
            "recommends_action": True,
        },
        verify=verify,
    )
    harness = install(monkeypatch, model)
    before_ids = pending_ids(session)
    before_status = condition_status(session)

    result = invoke(route_doctor_request, JANE_ID, text, "typed", session=session)

    assert_request(session, result, text=text, channel="typed", route="clinical_question")
    assert_typed_silent(result)
    assert result["suggestions"] == []
    assert pending_ids(session) == before_ids
    assert result["answer"]["text"] == expected_text
    assert "An extra claim is not supported." not in result["answer"]["text"]
    assert result["answer"]["citations"] == citations
    assert citation_tiers(result["answer"]["citations"]) == {"baseline", "guideline", "chart"}
    chart_hit = result["answer"]["citations"][2]
    assert chart_hit["tier"] == "chart"
    assert chart_hit["locator"].startswith("note:") or chart_hit["locator"].startswith(
        "observation:"
    )
    assert chart_hit["source_id"]
    assert chart_hit["passage"]
    assert condition_status(session) == before_status
    assert model.calls[0] == ("classify", {"text": text})
    research_payload = payloads(model, "research")[0]
    assert research_payload["text"] == text
    assert isinstance(research_payload["context"], dict)
    assert "notes" in research_payload
    assert_model_leaked_tool_text(research_payload)
    assert any(call["name"] == "search_patient_notes" for call in research_payload["tool_calls"])
    assert payloads(model, "verify")
    assert_deidentified_evidence(harness.evidence_calls)
    assert_context_call(harness)
    assert harness.propose_calls == []


def test_clinical_question_keeps_cited_findings_when_it_recommends_action(seeded_db, monkeypatch):
    session = seeded_db.session
    text = "What are the benefits and harms of this treatment?"
    literature = literature_citation()
    web = {
        "source_id": "web:psyllium-harms",
        "title": "Psyllium overview",
        "passage": "Psyllium can cause bloating and may interfere with drug absorption.",
        "locator": "https://medlineplus.gov/druginfo/natural/866.html",
        "tier": "web",
    }
    citations = [literature, web]
    sentence = "Published studies and a public page describe benefits and harms."

    def verify(payload):
        assert payload["allow_any_tier"] is True
        assert payload["citations"] == citations
        return {
            "supported": [{"sentence": sentence, "citation_indexes": [0, 1]}],
            "removed": [],
        }

    model = DoctorModel(
        route="clinical_question",
        research={
            "tool_calls": evidence_tool_calls(include_notes=True),
            "answer": {"text": sentence, "citations": citations},
            "recommends_action": True,
        },
        verify=verify,
    )
    harness = install(monkeypatch, model)

    result = invoke(route_doctor_request, JANE_ID, text, "typed", session=session)

    assert_request(session, result, text=text, channel="typed", route="clinical_question")
    assert_typed_silent(result)
    assert result["suggestions"] == []
    assert result["answer"]["text"] == sentence
    assert result["answer"]["citations"] == citations
    assert payloads(model, "verify")
    assert_deidentified_evidence(harness.evidence_calls)
    assert harness.propose_calls == []


def test_clinical_question_without_recommendation_keeps_literature(seeded_db, monkeypatch):
    session = seeded_db.session
    text = "What does the literature say about family history?"
    literature = literature_citation()
    sentence = "Published studies describe earlier screening after family history."

    def verify(payload):
        assert payload["citations"] == [literature]
        return {
            "supported": [{"sentence": sentence, "citation_indexes": [0]}],
            "removed": [],
        }

    model = DoctorModel(
        route="clinical_question",
        research={
            "tool_calls": evidence_tool_calls(include_notes=True),
            "answer": {"text": sentence, "citations": [literature]},
            "recommends_action": False,
        },
        verify=verify,
    )
    harness = install(monkeypatch, model)

    result = invoke(route_doctor_request, JANE_ID, text, "typed", session=session)

    assert_request(session, result, text=text, channel="typed", route="clinical_question")
    assert result["suggestions"] == []
    assert result["answer"]["text"] == sentence
    assert result["answer"]["citations"] == [literature]
    assert_deidentified_evidence(harness.evidence_calls)
    assert harness.propose_calls == []


def test_check_screenings_up_to_date(seeded_db, monkeypatch):
    session = seeded_db.session
    text = "Are her screenings up to date?"
    before_ids = pending_ids(session)
    before_reminders = reminder_snapshot(session)
    before_status = condition_status(session)
    jane_screening(session)
    model = DoctorModel(
        route="check_screenings",
        reminders={
            "up_to_date": True,
            "answer": "Screenings are up to date.",
            "suggestions": [],
            "tool_calls": [],
        },
    )
    harness = install(monkeypatch, model)

    result = invoke(route_doctor_request, JANE_ID, text, "typed", session=session)

    assert_request(session, result, text=text, channel="typed", route="check_screenings")
    assert_typed_silent(result)
    assert result["suggestions"] == []
    assert pending_ids(session) == before_ids
    assert isinstance(result["answer"], dict)
    assert set(result["answer"]) == {"text", "citations"}
    assert "up to date" in result["answer"]["text"].lower()
    assert reminder_snapshot(session) == before_reminders
    assert condition_status(session) == before_status
    assert model.calls[0] == ("classify", {"text": text})
    reminder_payload = payloads(model, "reminders")[0]
    assert reminder_payload["trigger"] == "doctor_request"
    assert_rules(reminder_payload)
    assert_context_call(harness)
    assert harness.propose_calls == []


def test_check_screenings_departure_proposes_reminder_change(seeded_db, monkeypatch):
    session = seeded_db.session
    text = "Check colorectal cancer screening."
    citations = [baseline_citation(), guideline_citation()]
    suggestion = reminder_change(citations)
    before_ids = pending_ids(session)
    before_reminders = reminder_snapshot(session)
    before_status = condition_status(session)
    screening = jane_screening(session)
    model = DoctorModel(
        route="check_screenings",
        reminders={
            "up_to_date": False,
            "answer": None,
            "suggestions": [suggestion],
            "tool_calls": evidence_tool_calls(),
        },
    )
    harness = install(monkeypatch, model)

    result = invoke(route_doctor_request, JANE_ID, text, "typed", session=session)

    assert_request(session, result, text=text, channel="typed", route="check_screenings")
    assert_typed_silent(result)
    assert result["answer"] is None
    assert_new_pending(session, before_ids, result["suggestions"])
    stored = result["suggestions"][0]
    assert stored["kind"] == "reminder_change"
    assert stored["source"] == "reminder_agent"
    assert stored["target_table"] == "reminder_schedule"
    assert stored["status"] == "pending"
    assert stored["after"] == {"due_on": "2026-12-01", "status": "scheduled"}
    assert_departure_reason(stored["reason"])
    tiers = citation_tiers(stored["citations"])
    assert "baseline" in tiers
    assert tiers & {"guideline", "literature"}
    assert screening["due_on"] == jane_screening(session)["due_on"]
    assert reminder_snapshot(session) == before_reminders
    assert condition_status(session) == before_status
    reminder_payload = payloads(model, "reminders")[0]
    assert reminder_payload["trigger"] == "doctor_request"
    assert_rules(reminder_payload)
    assert_model_leaked_tool_text(reminder_payload)
    verify_payloads = payloads(model, "verify")
    assert any(item["text"] == DEPARTURE_REASON for item in verify_payloads)
    assert_deidentified_evidence(harness.evidence_calls)
    assert_context_call(harness)
    assert_proposed(harness, "reminder_change")
