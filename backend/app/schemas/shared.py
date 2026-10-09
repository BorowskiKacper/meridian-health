"""Shared citation, suggestion, and error schemas."""

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, model_validator

CitationTier = Literal[
    "baseline",
    "guideline",
    "literature",
    "chart",
    "payer",
    "web",
]

SuggestionKind = Literal[
    "field_update",
    "reminder_change",
    "soap_note",
    "observation",
    "plan_item",
]

SuggestionStatus = Literal["pending", "approved", "rejected"]

TargetTable = Literal[
    "conditions",
    "medications",
    "family_history",
    "observations",
    "notes",
    "reminder_schedule",
]

ValidationFlag = Literal["low_confidence", "out_of_range"]

SuggestionSource = Literal[
    "chart_agent",
    "reminder_agent",
    "lab_report",
    "research_add_to_plan",
]

ErrorCode = Literal[
    "validation_error",
    "wrong_role",
    "not_found",
    "invalid_state",
]

_TABLE_KEYS: dict[TargetTable, frozenset[str]] = {
    "conditions": frozenset({"name", "status", "onset_date", "body_region_key"}),
    "medications": frozenset(
        {
            "name",
            "dose",
            "route",
            "frequency",
            "status",
            "start_date",
            "body_region_key",
        }
    ),
    "family_history": frozenset({"relationship", "condition", "age_at_diagnosis"}),
    "observations": frozenset(
        {"name", "value", "unit", "observed_at", "body_region_key"}
    ),
    "notes": frozenset({"body"}),
    "reminder_schedule": frozenset({"name", "due_on", "status"}),
}

_STATUS_VALUES: dict[str, frozenset[str]] = {
    "conditions": frozenset({"active", "resolved", "controlled"}),
    "medications": frozenset({"active", "stopped"}),
    "reminder_schedule": frozenset({"scheduled", "paused", "sent", "done"}),
}


def _uuid_string(value: Any) -> str:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str):
        try:
            return str(UUID(value))
        except ValueError as exc:
            raise ValueError("must be a UUID string") from exc
    raise ValueError("must be a UUID string")


UuidString = Annotated[str, BeforeValidator(_uuid_string)]


class Citation(BaseModel):
    source_id: str
    title: str
    passage: str
    locator: str
    tier: CitationTier


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class Suggestion(BaseModel):
    id: UuidString
    patient_id: UuidString
    request_id: UuidString | None
    kind: SuggestionKind
    status: SuggestionStatus
    target_table: TargetTable
    target_id: UuidString | None
    before: dict[str, Any]
    after: dict[str, Any]
    reason: str
    confidence: float
    citations: list[Citation]
    validation_flags: list[ValidationFlag]
    source: SuggestionSource
    unconfirmed: bool = False

    @model_validator(mode="after")
    def _allowlisted_changes(self) -> "Suggestion":
        allowed = _TABLE_KEYS[self.target_table]
        statuses = _STATUS_VALUES.get(self.target_table)
        for label, patch in (("before", self.before), ("after", self.after)):
            unknown = set(patch) - allowed
            if unknown:
                names = ", ".join(sorted(unknown))
                raise ValueError(
                    f"{label} contains keys that are not allowed for "
                    f"{self.target_table}: {names}"
                )
            if statuses is not None and "status" in patch:
                if patch["status"] not in statuses:
                    raise ValueError(
                        f"{label} status is not allowed for {self.target_table}"
                    )
        return self
