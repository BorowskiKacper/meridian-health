from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.api.errors import as_aware, finish, reject_unless_secretary

router = APIRouter()


class AppointmentCreate(BaseModel):
    patient_id: str
    starts_at: datetime
    ends_at: datetime
    reason: str


class AppointmentUpdate(BaseModel):
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    reason: str | None = None
    status: str | None = None


def _secretary(x_role: str | None):
    return reject_unless_secretary(x_role)


@router.get("/appointments")
def list_appointments(
    patient_id: str | None = None,
    on: date | None = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
):
    denied = _secretary(x_role)
    if denied is not None:
        return denied
    import app.api.db as api_db
    import app.services.appointments as appointments

    with api_db.get_session() as session:
        result = appointments.list_appointments(patient_id, on, session=session)
        return finish(result)


@router.post("/appointments")
def create_appointment(
    body: AppointmentCreate,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
):
    denied = _secretary(x_role)
    if denied is not None:
        return denied
    import app.api.db as api_db
    import app.services.appointments as appointments

    with api_db.get_session() as session:
        result = appointments.create_appointment(
            body.patient_id,
            as_aware(body.starts_at),
            as_aware(body.ends_at),
            body.reason,
            session=session,
        )
        return finish(result)


@router.put("/appointments/{appointment_id}")
def update_appointment(
    appointment_id: str,
    body: AppointmentUpdate,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
):
    denied = _secretary(x_role)
    if denied is not None:
        return denied
    import app.api.db as api_db
    import app.services.appointments as appointments

    with api_db.get_session() as session:
        result = appointments.update_appointment(
            appointment_id,
            starts_at=as_aware(body.starts_at),
            ends_at=as_aware(body.ends_at),
            reason=body.reason,
            status=body.status,
            session=session,
        )
        return finish(result)
