from fastapi import APIRouter

router = APIRouter()


@router.post("/secretary/requests")
def create_secretary_request(patient_id, text):
    raise NotImplementedError
