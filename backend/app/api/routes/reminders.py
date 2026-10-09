from fastapi import APIRouter

router = APIRouter()


@router.put("/patients/{patient_id}/reminders/{reminder_id}")
def update_reminder(patient_id, reminder_id, due_on=None, status=None):
    raise NotImplementedError


@router.post("/demo/run-reminders")
def run_reminders(as_of=None):
    raise NotImplementedError
