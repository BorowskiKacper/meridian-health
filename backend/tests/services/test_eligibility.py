from datetime import date
from pathlib import Path

from app.db.repositories import (
    get_coverage_by_patient,
    insert_patient,
    list_conditions_by_patient,
    list_eligibility_checks_by_patient,
)
from app.services.eligibility import check_eligibility

JANE_ID = "11111111-1111-4111-8111-111111111111"
UNCOVERED_PATIENT_ID = "44444444-4444-4444-8444-444444444444"
UNKNOWN_PATIENT_ID = "99999999-9999-4999-8999-999999999999"
ORDER_TEXT = "screening colonoscopy"
SUMMARY = "Coverage is active. A preventive visit copay is $30."
PRIOR_AUTH_NOTE = "This plan asks for prior auth for this order."

PAYER_CITATION = {
    "source_id": "payer:colonoscopy",
    "title": "Northwind prior auth",
    "passage": "Screening colonoscopy requires prior authorization.",
    "locator": "Northwind Health, Prior Authorization List",
    "tier": "payer",
}
PAYER_PASSAGES = [PAYER_CITATION]

FORBIDDEN_IDENTIFIERS = (
    JANE_ID,
    "NW-1001",
    "+15555550101",
    "Jane Doe",
    "1974-03-15",
)

ELIGIBILITY_SOURCE = (
    Path(__file__).resolve().parents[2] / "app" / "services" / "eligibility.py"
)


def invoke(fn, *args, session, **kwargs):
    import inspect

    if "session" in inspect.signature(fn).parameters:
        kwargs["session"] = session
    return fn(*args, **kwargs)


def install_fakes(monkeypatch, summary, prior_auth_required, prior_auth_note):
    prompts = []
    payer_texts = []

    def ask_model(prompt):
        prompts.append(prompt)
        return {
            "summary": summary,
            "prior_auth_required": prior_auth_required,
            "prior_auth_note": prior_auth_note,
        }

    def search_payer_docs(text):
        payer_texts.append(text)
        return {"passages": [dict(PAYER_CITATION)]}

    monkeypatch.setattr("app.services.eligibility.ask_model", ask_model, raising=False)
    monkeypatch.setattr(
        "app.evidence.search_payer_docs",
        search_payer_docs,
        raising=False,
    )
    return prompts, payer_texts


def assert_jane_coverage(coverage):
    assert coverage["payer_name"] == "Northwind Health"
    assert coverage["member_id"] == "NW-1001"
    assert coverage["plan_name"] == "PPO"
    assert coverage["active"] is True
    assert coverage["deductible_remaining"] == 400
    assert coverage["copay"] == 30
    assert coverage["benefits"] == [
        {"name": "Preventive colonoscopy", "detail": "Covered in network"}
    ]


def assert_deidentified(text):
    assert isinstance(text, str)
    for identifier in FORBIDDEN_IDENTIFIERS:
        assert identifier not in text


def assert_not_found(result):
    assert set(result) == {"error"}
    error = result["error"]
    assert set(error) == {"code", "message"}
    assert error["code"] == "not_found"
    message = error["message"]
    assert isinstance(message, str) and message.strip()


def only_eligibility_row(session, patient_id):
    rows = list_eligibility_checks_by_patient(session, patient_id)
    assert len(rows) == 1
    return rows[0]


def test_null_order_skips_prior_auth_and_stores_blank_text(seeded_db, monkeypatch):
    session = seeded_db.session
    conditions_before = list_conditions_by_patient(session, JANE_ID)
    summary = "Coverage is active."
    prompts, payer_texts = install_fakes(
        monkeypatch,
        summary=summary,
        prior_auth_required=True,
        prior_auth_note=PRIOR_AUTH_NOTE,
    )

    result = invoke(check_eligibility, JANE_ID, None, session=session)

    assert_jane_coverage(result["coverage"])
    assert result["summary"] == summary
    assert result["prior_auth"] is None
    assert payer_texts == []
    assert len(prompts) == 1
    assert_deidentified(prompts[0])
    row = only_eligibility_row(session, JANE_ID)
    assert row["patient_id"] == JANE_ID
    assert row["order_text"] == ""
    assert row["prior_auth_note"] == ""
    assert row["citations"] == []
    assert row["summary"] == summary
    assert list_conditions_by_patient(session, JANE_ID) == conditions_before


def test_order_without_prior_auth_question_does_not_search_payer_docs(
    seeded_db, monkeypatch
):
    session = seeded_db.session
    prompts, payer_texts = install_fakes(
        monkeypatch,
        summary=SUMMARY,
        prior_auth_required=False,
        prior_auth_note=PRIOR_AUTH_NOTE,
    )

    result = invoke(check_eligibility, JANE_ID, ORDER_TEXT, session=session)

    assert_jane_coverage(result["coverage"])
    assert result["summary"] == SUMMARY
    assert result["prior_auth"] is None
    assert payer_texts == []
    assert len(prompts) == 1
    assert_deidentified(prompts[0])
    row = only_eligibility_row(session, JANE_ID)
    assert row["patient_id"] == JANE_ID
    assert row["order_text"] == ORDER_TEXT
    assert row["summary"] == SUMMARY
    assert row["prior_auth_note"] == ""
    assert row["citations"] == []


def test_prior_auth_question_cites_payer_docs_without_identifiers(
    seeded_db, monkeypatch
):
    session = seeded_db.session
    prompts, payer_texts = install_fakes(
        monkeypatch,
        summary=SUMMARY,
        prior_auth_required=True,
        prior_auth_note=PRIOR_AUTH_NOTE,
    )

    result = invoke(check_eligibility, JANE_ID, ORDER_TEXT, session=session)

    assert_jane_coverage(result["coverage"])
    assert result["summary"] == SUMMARY
    assert result["prior_auth"]["note"] == PRIOR_AUTH_NOTE
    assert result["prior_auth"]["citations"] == PAYER_PASSAGES
    assert len(payer_texts) == 1
    assert_deidentified(payer_texts[0])
    assert len(prompts) == 1
    assert_deidentified(prompts[0])
    row = only_eligibility_row(session, JANE_ID)
    assert row["patient_id"] == JANE_ID
    assert row["order_text"] == ORDER_TEXT
    assert row["summary"] == SUMMARY
    assert row["prior_auth_note"] == PRIOR_AUTH_NOTE
    assert row["citations"] == PAYER_PASSAGES
    assert row["coverage_id"] == get_coverage_by_patient(session, JANE_ID)["id"]


def test_patient_without_coverage_is_not_found(seeded_db, monkeypatch):
    session = seeded_db.session
    insert_patient(
        session,
        {
            "id": UNCOVERED_PATIENT_ID,
            "display_name": "Casey Noplan",
            "date_of_birth": date(1988, 7, 4),
            "sex": "female",
            "sms_opt_in": False,
            "phone_e164": "+15555550188",
        },
    )
    prompts, payer_texts = install_fakes(
        monkeypatch,
        summary=SUMMARY,
        prior_auth_required=True,
        prior_auth_note=PRIOR_AUTH_NOTE,
    )

    result = invoke(
        check_eligibility,
        UNCOVERED_PATIENT_ID,
        ORDER_TEXT,
        session=session,
    )

    assert_not_found(result)
    assert prompts == []
    assert payer_texts == []
    assert list_eligibility_checks_by_patient(session, UNCOVERED_PATIENT_ID) == []
    assert list_eligibility_checks_by_patient(session, JANE_ID) == []


def test_unknown_patient_is_not_found(seeded_db, monkeypatch):
    session = seeded_db.session
    prompts, payer_texts = install_fakes(
        monkeypatch,
        summary=SUMMARY,
        prior_auth_required=True,
        prior_auth_note=PRIOR_AUTH_NOTE,
    )

    result = invoke(check_eligibility, UNKNOWN_PATIENT_ID, ORDER_TEXT, session=session)

    assert_not_found(result)
    assert prompts == []
    assert payer_texts == []
    assert list_eligibility_checks_by_patient(session, UNKNOWN_PATIENT_ID) == []
    assert list_eligibility_checks_by_patient(session, JANE_ID) == []


def test_eligibility_source_does_not_reference_stedi_or_mcp():
    source = ELIGIBILITY_SOURCE.read_text(encoding="utf-8")
    assert "stedi" not in source.lower()
    assert "app.mcp" not in source
