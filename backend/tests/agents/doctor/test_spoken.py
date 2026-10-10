from app.agents.doctor import route_doctor_request

from support import (
    JANE_ID,
    DoctorModel,
    assert_typed_silent,
    baseline_citation,
    install,
    invoke,
    reminder_change,
)


CHART_REASON = "Recent readings show hypertension is controlled."
CLINICAL_TEXT = "LDL is above the range discussed in the cited guideline."
CITATION_TITLE = "Secret Citation Title"
SCREENING_REASON = "USPSTF baseline: start at 45 for average risk."


def _clinical_model(text):
    citation = baseline_citation()
    citation["title"] = CITATION_TITLE
    return DoctorModel(
        route="clinical_question",
        research={
            "tool_calls": [],
            "answer": {"text": text, "citations": [citation]},
            "recommends_action": False,
        },
    )


def _screening_with_suggestions():
    return DoctorModel(
        route="check_screenings",
        reminders={
            "tool_calls": [],
            "suggestions": [reminder_change([baseline_citation()], SCREENING_REASON)],
            "answer": "A change is proposed.",
            "up_to_date": False,
        },
    )


def test_typed_requests_stay_silent(seeded_db, monkeypatch):
    session = seeded_db.session
    cases = [
        DoctorModel(route="chart_update", chart={"suggestions": []}),
        _clinical_model(CLINICAL_TEXT),
        DoctorModel(
            route="check_screenings",
            reminders={
                "tool_calls": [],
                "suggestions": [],
                "answer": "Screenings are up to date.",
                "up_to_date": True,
            },
        ),
    ]
    for model in cases:
        install(monkeypatch, model)
        result = invoke(
            route_doctor_request,
            JANE_ID,
            "typed request",
            "typed",
            session=session,
        )
        assert_typed_silent(result)


def test_voice_chart_update_speaks_the_reasons(seeded_db, monkeypatch):
    session = seeded_db.session
    suggestion = reminder_change([baseline_citation()], CHART_REASON)
    suggestion["kind"] = "field_update"
    suggestion["target_table"] = "conditions"
    suggestion["source"] = "chart_agent"
    suggestion["before"] = {"status": "active"}
    suggestion["after"] = {"status": "controlled"}
    install(
        monkeypatch,
        DoctorModel(route="chart_update", chart={"suggestions": [suggestion]}),
    )

    result = invoke(
        route_doctor_request,
        JANE_ID,
        "Mark hypertension controlled.",
        "voice",
        session=session,
    )

    assert result["spoken_text"] == f"I will propose these chart updates. {CHART_REASON}"
    assert result["audio_base64"] is None


def test_voice_clinical_question_speaks_the_answer(seeded_db, monkeypatch):
    session = seeded_db.session
    install(monkeypatch, _clinical_model(CLINICAL_TEXT))

    result = invoke(
        route_doctor_request,
        JANE_ID,
        "What about LDL?",
        "voice",
        session=session,
    )

    assert result["spoken_text"] == CLINICAL_TEXT
    assert CITATION_TITLE not in result["spoken_text"]
    assert result["audio_base64"] is None


def test_voice_screening_with_suggestions_matches_the_chart_read_back(
    seeded_db, monkeypatch
):
    session = seeded_db.session
    install(monkeypatch, _screening_with_suggestions())

    result = invoke(
        route_doctor_request,
        JANE_ID,
        "Check screenings.",
        "voice",
        session=session,
    )

    assert result["suggestions"]
    assert result["spoken_text"] == (
        f"I will propose these chart updates. {SCREENING_REASON}"
    )
    assert result["audio_base64"] is None


def test_voice_screening_up_to_date_speaks_the_answer(seeded_db, monkeypatch):
    session = seeded_db.session
    answer = "Screenings are up to date."
    install(
        monkeypatch,
        DoctorModel(
            route="check_screenings",
            reminders={
                "tool_calls": [],
                "suggestions": [],
                "answer": answer,
                "up_to_date": True,
            },
        ),
    )

    result = invoke(
        route_doctor_request,
        JANE_ID,
        "Check screenings.",
        "voice",
        session=session,
    )

    assert result["spoken_text"] == answer
    assert result["audio_base64"] is None


def test_blank_answer_is_not_spoken(seeded_db, monkeypatch):
    session = seeded_db.session
    install(monkeypatch, _clinical_model("   "))

    result = invoke(
        route_doctor_request,
        JANE_ID,
        "What about LDL?",
        "voice",
        session=session,
    )

    assert result["spoken_text"] is None
    assert result["audio_base64"] is None
