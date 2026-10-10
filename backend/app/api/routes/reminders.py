from datetime import date, datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.errors import finish

router = APIRouter()


class ReminderUpdate(BaseModel):
    due_on: date | None = None
    status: str | None = None


class RunRemindersBody(BaseModel):
    as_of: date | None = None


@router.get("/patients/{patient_id}/reminders")
def list_reminders(patient_id: str):
    import app.api.db as api_db
    import app.services.reminders as reminders

    session = api_db.get_session()
    result = reminders.list_patient_reminders(patient_id, session=session)
    return finish(result)


@router.put("/patients/{patient_id}/reminders/{reminder_id}")
def update_reminder(patient_id: str, reminder_id: str, body: ReminderUpdate):
    import app.api.db as api_db
    import app.services.reminders as reminders

    session = api_db.get_session()
    result = reminders.update_reminder(
        patient_id,
        reminder_id,
        body.due_on,
        body.status,
        session=session,
    )
    return finish(result)


@router.post("/demo/run-reminders")
def run_reminders(body: RunRemindersBody | None = None):
    import app.api.db as api_db
    import app.services.reminders as reminders

    session = api_db.get_session()
    if body is None or body.as_of is None:
        as_of = datetime.now(timezone.utc).date()
    else:
        as_of = body.as_of
    result = reminders.send_due_reminders(as_of, session=session)
    return finish(result)
