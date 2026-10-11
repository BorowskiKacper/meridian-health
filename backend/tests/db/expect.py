from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

UTC = timezone.utc

UUID_KEYS = frozenset(
    {
        "id",
        "patient_id",
        "document_id",
        "source_suggestion_id",
        "request_id",
        "target_id",
        "suggestion_id",
        "reminder_id",
        "rule_id",
        "coverage_id",
    }
)
NULLABLE_UUID_KEYS = frozenset(
    {
        "document_id",
        "source_suggestion_id",
        "request_id",
        "target_id",
        "suggestion_id",
        "reminder_id",
        "coverage_id",
    }
)
DATE_KEYS = frozenset({"date_of_birth", "onset_date", "start_date", "due_on"})
INSTANT_KEYS = frozenset(
    {
        "observed_at",
        "occurred_at",
        "created_at",
        "uploaded_at",
        "starts_at",
        "ends_at",
    }
)
BOOL_KEYS = frozenset({"email_opt_in", "active"})
JSON_DICT_KEYS = frozenset({"before", "after"})
JSON_LIST_KEYS = frozenset({"benefits", "citations", "validation_flags"})
STRING_KEYS = frozenset(
    {
        "display_name",
        "sex",
        "email",
        "name",
        "status",
        "dose",
        "route",
        "frequency",
        "relationship",
        "condition",
        "unit",
        "source",
        "encounter_type",
        "summary",
        "body",
        "storage_key",
        "media_type",
        "region_key",
        "body_region_key",
        "mesh_name",
        "specialty_key",
        "guideline_source_id",
        "kind",
        "target_table",
        "reason",
        "action",
        "detail",
        "to_email",
        "provider_id",
        "payer_name",
        "member_id",
        "plan_name",
        "order_text",
        "prior_auth_note",
        "channel",
        "role",
        "transcript",
        "route",
    }
)

PATIENT_KEYS = frozenset(
    {"id", "display_name", "date_of_birth", "sex", "email_opt_in", "email"}
)
CONDITION_KEYS = frozenset(
    {"id", "patient_id", "name", "status", "onset_date", "body_region_key"}
)
MEDICATION_KEYS = frozenset(
    {
        "id",
        "patient_id",
        "name",
        "dose",
        "route",
        "frequency",
        "status",
        "start_date",
        "body_region_key",
    }
)
FAMILY_HISTORY_KEYS = frozenset(
    {"id", "patient_id", "relationship", "condition", "age_at_diagnosis"}
)
OBSERVATION_KEYS = frozenset(
    {
        "id",
        "patient_id",
        "name",
        "value",
        "unit",
        "observed_at",
        "source",
        "document_id",
        "body_region_key",
    }
)
ENCOUNTER_KEYS = frozenset(
    {"id", "patient_id", "encounter_type", "occurred_at", "summary"}
)
NOTE_KEYS = frozenset(
    {"id", "patient_id", "body", "embedding", "source_suggestion_id", "created_at"}
)
DOCUMENT_KEYS = frozenset(
    {"id", "patient_id", "storage_key", "media_type", "uploaded_at"}
)
BODY_REGION_KEYS = frozenset({"region_key", "display_name", "mesh_name"})
SPECIALTY_FOCUS_KEYS = frozenset({"specialty_key", "region_key"})
REMINDER_RULE_KEYS = frozenset({"id", "name", "baseline_age", "guideline_source_id"})
REMINDER_KEYS = frozenset(
    {"id", "patient_id", "rule_id", "name", "due_on", "status"}
)
SUGGESTION_KEYS = frozenset(
    {
        "id",
        "patient_id",
        "request_id",
        "kind",
        "status",
        "target_table",
        "target_id",
        "before",
        "after",
        "reason",
        "confidence",
        "citations",
        "validation_flags",
        "source",
    }
)
AUDIT_LOG_KEYS = frozenset(
    {"id", "patient_id", "suggestion_id", "action", "detail", "created_at"}
)
EMAIL_MESSAGE_KEYS = frozenset(
    {"id", "patient_id", "reminder_id", "to_email", "body", "provider_id", "status"}
)
COVERAGE_KEYS = frozenset(
    {
        "id",
        "patient_id",
        "payer_name",
        "member_id",
        "plan_name",
        "active",
        "deductible_remaining",
        "copay",
        "benefits",
    }
)
ELIGIBILITY_CHECK_KEYS = frozenset(
    {
        "id",
        "patient_id",
        "coverage_id",
        "order_text",
        "summary",
        "prior_auth_note",
        "citations",
        "created_at",
    }
)
APPOINTMENT_KEYS = frozenset(
    {"id", "patient_id", "starts_at", "ends_at", "reason", "status"}
)
REQUEST_KEYS = frozenset(
    {"id", "patient_id", "channel", "role", "transcript", "route", "created_at"}
)


def assert_value(key, actual, expected):
    if expected is None:
        assert actual is None
        return
    if key in UUID_KEYS:
        assert isinstance(actual, str)
        assert actual == expected
        UUID(actual)
        return
    if key == "embedding":
        assert isinstance(actual, list)
        assert len(actual) == len(expected)
        assert all(type(item) is float for item in actual)
        for got, want in zip(actual, expected):
            assert got == pytest.approx(want)
        return
    if isinstance(expected, datetime):
        assert isinstance(actual, datetime)
        assert actual.tzinfo is not None and actual.utcoffset() is not None
        assert actual.astimezone(UTC) == expected.astimezone(UTC)
        return
    if isinstance(expected, date):
        assert type(actual) is date
        assert actual == expected
        return
    if isinstance(expected, bool):
        assert type(actual) is bool
        assert actual is expected
        return
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        assert isinstance(actual, (int, float, Decimal))
        assert not isinstance(actual, bool)
        assert float(actual) == pytest.approx(float(expected))
        return
    if key in JSON_DICT_KEYS:
        assert isinstance(actual, dict)
    elif key in JSON_LIST_KEYS:
        assert isinstance(actual, list)
    elif isinstance(expected, str):
        assert isinstance(actual, str)
    assert actual == expected


def assert_contract(actual, expected):
    assert isinstance(actual, dict)
    assert set(actual) == set(expected)
    for key, value in expected.items():
        assert_value(key, actual[key], value)


def assert_row_types(row):
    assert isinstance(row, dict)
    for key, value in row.items():
        if key in UUID_KEYS:
            if value is None:
                assert key in NULLABLE_UUID_KEYS
            else:
                assert isinstance(value, str)
                UUID(value)
        elif key in DATE_KEYS:
            assert value is None or type(value) is date
        elif key in INSTANT_KEYS:
            assert isinstance(value, datetime)
            assert value.tzinfo is not None and value.utcoffset() is not None
        elif key in BOOL_KEYS:
            assert type(value) is bool
        elif key == "embedding":
            assert value is None or (
                isinstance(value, list) and all(type(item) is float for item in value)
            )
        elif key in JSON_DICT_KEYS:
            assert isinstance(value, dict)
        elif key in JSON_LIST_KEYS:
            assert isinstance(value, list)
        elif key in STRING_KEYS and value is not None:
            assert isinstance(value, str)


def assert_fields(actual, keys, **expected):
    assert isinstance(actual, dict)
    assert set(actual) == set(keys)
    assert_row_types(actual)
    for key, value in expected.items():
        assert_value(key, actual[key], value)
