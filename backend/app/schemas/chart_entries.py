from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Submission(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    submission_id: UUID


class Vitals(Submission):
    observed_at: AwareDatetime
    systolic: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    diastolic: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    weight_kg: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    pulse: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    respiratory_rate: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    temperature_f: float | None = Field(default=None, gt=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def validate_measurements(self):
        if (self.systolic is None) != (self.diastolic is None):
            raise ValueError('Record both blood-pressure values.')
        if all((v is None for v in (self.systolic, self.weight_kg, self.pulse, self.respiratory_rate, self.temperature_f))):
            raise ValueError('Enter at least one measurement.')
        if self.observed_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError('The measurement date cannot be in the future.')
        return self


class MedicationEntry(Submission):
    name: str = Field(min_length=1, max_length=200)
    dose: str = Field(min_length=1, max_length=200)
    route: str = Field(min_length=1, max_length=100)
    frequency: str = Field(min_length=1, max_length=200)
    status: Literal['active', 'stopped']
    start_date: date
    body_region_key: str


class AllergyEntry(Submission):
    substance: str = Field(min_length=1, max_length=200)
    category: Literal['drug', 'food', 'environmental']
    reaction: str = Field(min_length=1, max_length=500)
    severity: Literal['unknown', 'mild', 'moderate', 'severe', 'anaphylaxis']
    status: Literal['active', 'inactive']
    recorded_on: date


class ProblemEntry(Submission):
    name: str = Field(min_length=1, max_length=200)
    status: Literal['active', 'resolved']
    onset_date: date
    body_region_key: str


class VisitDraft(Submission):
    visit_date: date
    reason: str = Field(min_length=1, max_length=2000)
    assessment: str = Field(default='', max_length=12000)
    plan: str = Field(default='', max_length=12000)


class Review(Submission):
    kind: Literal['medications', 'allergies']
    record_ids: list[UUID]
    medication_use: dict[UUID, Literal['taking', 'not_taking', 'unknown']] = Field(default_factory=dict)
    note: str = Field(default='', max_length=2000)
    confirmed_with_patient: Literal[True]
    expected_version: str


class Inactivate(Submission):
    status: Literal['inactive']


class NoKnownDrugAllergies(Submission):
    recorded_on: date
    confirmed_with_patient: Literal[True]


class FollowUp(Submission):
    due_on: date
    status: Literal['scheduled', 'due', 'paused', 'done']
