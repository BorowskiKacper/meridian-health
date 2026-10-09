import copy

import pytest
from pydantic import ValidationError

from app.schemas import Citation, ErrorResponse, Suggestion

CONTRACT_CITATION = {
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

SUGGESTION_ID = "6f1b1c2a-3d4e-4f50-8a61-7b8c9d0e1f2a"
PATIENT_ID = "a1b2c3d4-e5f6-4789-a012-3456789abcde"

VALID_SUGGESTION = {
    "id": SUGGESTION_ID,
    "patient_id": PATIENT_ID,
    "request_id": None,
    "kind": "field_update",
    "status": "pending",
    "target_table": "conditions",
    "target_id": None,
    "before": {},
    "after": {"status": "controlled"},
    "reason": "Recent readings show the condition is controlled.",
    "confidence": 0.0,
    "citations": [CONTRACT_CITATION],
    "validation_flags": [],
    "source": "chart_agent",
    "unconfirmed": False,
}

CONTRACT_ERROR = {
    "error": {"code": "not_found", "message": "Patient was not found."}
}


def suggestion_payload(**overrides):
    payload = copy.deepcopy(VALID_SUGGESTION)
    payload.update(overrides)
    return payload


def assert_matches_payload(model, payload):
    assert model.model_dump(mode="json") == payload


def test_accepts_contract_citation():
    citation = Citation.model_validate(CONTRACT_CITATION)

    assert isinstance(citation, Citation)
    assert_matches_payload(citation, CONTRACT_CITATION)


def test_accepts_suggestion_with_citation():
    suggestion = Suggestion.model_validate(VALID_SUGGESTION)

    assert isinstance(suggestion, Suggestion)
    assert all(isinstance(item, Citation) for item in suggestion.citations)
    assert_matches_payload(suggestion, VALID_SUGGESTION)


def test_accepts_suggestion_when_unconfirmed_omitted():
    payload = suggestion_payload()
    del payload["unconfirmed"]

    suggestion = Suggestion.model_validate(payload)

    assert suggestion.unconfirmed is False
    assert_matches_payload(suggestion, {**payload, "unconfirmed": False})


def test_accepts_contract_error():
    error = ErrorResponse.model_validate(CONTRACT_ERROR)

    assert isinstance(error, ErrorResponse)
    assert_matches_payload(error, CONTRACT_ERROR)


@pytest.mark.parametrize("code", ["validation_error", "wrong_role", "invalid_state"])
def test_accepts_error_code(code):
    payload = {"error": {"code": code, "message": "Patient was not found."}}

    error = ErrorResponse.model_validate(payload)

    assert_matches_payload(error, payload)


def test_rejects_target_table_outside_allowlist():
    payload = suggestion_payload(target_table="encounters")

    with pytest.raises(ValidationError):
        Suggestion.model_validate(payload)


def test_rejects_after_key_outside_table_allowlist():
    payload = suggestion_payload(after={"dose": "10mg"})

    with pytest.raises(ValidationError):
        Suggestion.model_validate(payload)


def test_rejects_condition_status_outside_allowlist():
    payload = suggestion_payload(after={"status": "paused"})

    with pytest.raises(ValidationError):
        Suggestion.model_validate(payload)


def test_rejects_medication_status_outside_allowlist():
    payload = suggestion_payload(
        target_table="medications",
        after={"status": "resolved"},
    )

    with pytest.raises(ValidationError):
        Suggestion.model_validate(payload)


def test_rejects_reminder_status_outside_allowlist():
    payload = suggestion_payload(
        target_table="reminder_schedule",
        after={"status": "active"},
    )

    with pytest.raises(ValidationError):
        Suggestion.model_validate(payload)


def test_rejects_citation_tier_outside_allowlist():
    payload = {**CONTRACT_CITATION, "tier": "blog"}

    with pytest.raises(ValidationError):
        Citation.model_validate(payload)


def test_rejects_error_missing_code():
    payload = {"error": {"message": "Patient was not found."}}

    with pytest.raises(ValidationError):
        ErrorResponse.model_validate(payload)


def test_rejects_before_key_outside_table_allowlist():
    payload = suggestion_payload(before={"dose": "10mg"})

    with pytest.raises(ValidationError):
        Suggestion.model_validate(payload)


def test_rejects_suggestion_status_scheduled():
    payload = suggestion_payload(status="scheduled")

    with pytest.raises(ValidationError):
        Suggestion.model_validate(payload)
