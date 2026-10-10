"""SQLAlchemy models for the Tiger tables in the database contract."""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PlainText(Text):
    cache_ok = True


class PlainString(String):
    cache_ok = True


class PlainJSONB(JSONB):
    cache_ok = True


class PlainVector(Vector):
    cache_ok = True

    def get_col_spec(self, **kw):
        return f"{super().get_col_spec(**kw)} STORAGE PLAIN"


# Inline storage keeps CREATE TABLE from adding toast indexes in pg_toast.
# The db tests reject any new object outside the private schema.
@compiles(PlainText, "postgresql")
def _compile_plain_text(_type, _compiler, **_kw):
    return "TEXT STORAGE PLAIN"


@compiles(PlainString, "postgresql")
def _compile_plain_string(type_, _compiler, **_kw):
    if type_.length is None:
        return "VARCHAR STORAGE PLAIN"
    return f"VARCHAR({type_.length}) STORAGE PLAIN"


@compiles(PlainJSONB, "postgresql")
def _compile_plain_jsonb(_type, _compiler, **_kw):
    return "JSONB STORAGE PLAIN"


def _uuid_pk():
    return mapped_column(Uuid(as_uuid=True), primary_key=True)


def _uuid_fk(table, *, nullable=False):
    return mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{table}.id"),
        nullable=nullable,
    )


def _region_fk():
    return mapped_column(
        PlainString,
        ForeignKey("body_regions.region_key"),
        nullable=False,
    )


def _required_text():
    return mapped_column(PlainText, nullable=False)


def _required_string():
    return mapped_column(PlainString, nullable=False)


def _instant():
    return mapped_column(DateTime(timezone=True), nullable=False)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = _uuid_pk()
    display_name: Mapped[str] = _required_string()
    date_of_birth: Mapped[object] = mapped_column(Date, nullable=False)
    sex: Mapped[str] = _required_string()
    sms_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False)
    phone_e164: Mapped[str] = _required_string()


class Condition(Base):
    __tablename__ = "conditions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    name: Mapped[str] = _required_string()
    status: Mapped[str] = _required_string()
    onset_date: Mapped[object] = mapped_column(Date, nullable=False)
    body_region_key: Mapped[str] = _region_fk()


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    name: Mapped[str] = _required_string()
    dose: Mapped[str] = _required_string()
    route: Mapped[str] = _required_string()
    frequency: Mapped[str] = _required_string()
    status: Mapped[str] = _required_string()
    start_date: Mapped[object] = mapped_column(Date, nullable=False)
    body_region_key: Mapped[str] = _region_fk()


class Allergy(Base):
    __tablename__ = "allergies"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    substance: Mapped[str] = _required_string()
    # drug, food, environmental, or nkda for a verified "no known drug allergies".
    category: Mapped[str] = _required_string()
    reaction: Mapped[str] = _required_string()
    # none, mild, moderate, severe, anaphylaxis
    severity: Mapped[str] = _required_string()
    status: Mapped[str] = _required_string()
    recorded_on: Mapped[object] = mapped_column(Date, nullable=False)
    verified_by: Mapped[str] = _required_string()


class FamilyHistory(Base):
    __tablename__ = "family_history"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    relationship: Mapped[str] = _required_string()
    condition: Mapped[str] = _required_string()
    age_at_diagnosis: Mapped[int] = mapped_column(Integer, nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    storage_key: Mapped[str] = _required_text()
    media_type: Mapped[str] = _required_string()
    uploaded_at: Mapped[object] = _instant()


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    name: Mapped[str] = _required_string()
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = _required_string()
    observed_at: Mapped[object] = _instant()
    source: Mapped[str] = _required_string()
    document_id: Mapped[uuid.UUID | None] = _uuid_fk("documents", nullable=True)
    body_region_key: Mapped[str] = _region_fk()


class Encounter(Base):
    __tablename__ = "encounters"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    encounter_type: Mapped[str] = _required_string()
    occurred_at: Mapped[object] = _instant()
    summary: Mapped[str] = _required_text()


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    channel: Mapped[str] = _required_string()
    role: Mapped[str] = _required_string()
    transcript: Mapped[str] = _required_text()
    route: Mapped[str] = _required_string()
    created_at: Mapped[object] = _instant()


class Suggestion(Base):
    __tablename__ = "ai_suggestions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    request_id: Mapped[uuid.UUID | None] = _uuid_fk("requests", nullable=True)
    kind: Mapped[str] = _required_string()
    status: Mapped[str] = _required_string()
    target_table: Mapped[str] = _required_string()
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    before: Mapped[dict] = mapped_column(PlainJSONB, nullable=False)
    after: Mapped[dict] = mapped_column(PlainJSONB, nullable=False)
    reason: Mapped[str] = _required_text()
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    citations: Mapped[list] = mapped_column(PlainJSONB, nullable=False)
    validation_flags: Mapped[list] = mapped_column(PlainJSONB, nullable=False)
    source: Mapped[str] = _required_string()


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    body: Mapped[str] = _required_text()
    embedding: Mapped[list[float] | None] = mapped_column(PlainVector(768), nullable=True)
    source_suggestion_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "ai_suggestions",
        nullable=True,
    )
    created_at: Mapped[object] = _instant()


class BodyRegion(Base):
    __tablename__ = "body_regions"

    region_key: Mapped[str] = mapped_column(PlainString, primary_key=True)
    display_name: Mapped[str] = _required_string()
    mesh_name: Mapped[str] = _required_string()


class SpecialtyFocus(Base):
    __tablename__ = "specialty_focus"

    specialty_key: Mapped[str] = mapped_column(PlainString, primary_key=True)
    region_key: Mapped[str] = mapped_column(
        PlainString,
        ForeignKey("body_regions.region_key"),
        primary_key=True,
    )


class ReminderRule(Base):
    __tablename__ = "reminder_rules"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = _required_string()
    baseline_age: Mapped[int] = mapped_column(Integer, nullable=False)
    guideline_source_id: Mapped[str] = _required_string()


class Reminder(Base):
    __tablename__ = "reminder_schedule"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    rule_id: Mapped[uuid.UUID] = _uuid_fk("reminder_rules")
    name: Mapped[str] = _required_string()
    due_on: Mapped[object] = mapped_column(Date, nullable=False)
    status: Mapped[str] = _required_string()


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    suggestion_id: Mapped[uuid.UUID | None] = _uuid_fk("ai_suggestions", nullable=True)
    action: Mapped[str] = _required_string()
    detail: Mapped[str] = _required_text()
    created_at: Mapped[object] = _instant()


class SmsMessage(Base):
    __tablename__ = "sms_messages"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    reminder_id: Mapped[uuid.UUID | None] = _uuid_fk("reminder_schedule", nullable=True)
    to_phone: Mapped[str] = _required_string()
    body: Mapped[str] = _required_text()
    twilio_sid: Mapped[str] = mapped_column(PlainString, nullable=False, unique=True)
    status: Mapped[str] = _required_string()


class Coverage(Base):
    __tablename__ = "coverages"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    payer_name: Mapped[str] = _required_string()
    member_id: Mapped[str] = _required_string()
    plan_name: Mapped[str] = _required_string()
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    deductible_remaining: Mapped[float] = mapped_column(Float, nullable=False)
    copay: Mapped[float] = mapped_column(Float, nullable=False)
    benefits: Mapped[list] = mapped_column(PlainJSONB, nullable=False)


class EligibilityCheck(Base):
    __tablename__ = "eligibility_checks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    coverage_id: Mapped[uuid.UUID | None] = _uuid_fk("coverages", nullable=True)
    order_text: Mapped[str] = _required_text()
    summary: Mapped[str] = _required_text()
    prior_auth_note: Mapped[str] = _required_text()
    citations: Mapped[list] = mapped_column(PlainJSONB, nullable=False)
    created_at: Mapped[object] = _instant()


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients")
    starts_at: Mapped[object] = _instant()
    ends_at: Mapped[object] = _instant()
    reason: Mapped[str] = _required_text()
    status: Mapped[str] = _required_string()
