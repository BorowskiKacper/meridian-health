from fastapi import APIRouter

router = APIRouter()


@router.get("/appointments")
def list_appointments(patient_id=None, on=None):
    raise NotImplementedError


@router.post("/appointments")
def create_appointment(patient_id, starts_at, ends_at, reason):
    raise NotImplementedError


@router.put("/appointments/{appointment_id}")
def update_appointment(
    appointment_id, starts_at=None, ends_at=None, reason=None, status=None
):
    raise NotImplementedError
