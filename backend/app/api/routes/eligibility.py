from fastapi import APIRouter

router = APIRouter()


@router.post("/patients/{patient_id}/eligibility")
def check_eligibility(patient_id, order_text=None):
    raise NotImplementedError
