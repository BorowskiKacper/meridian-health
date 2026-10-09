from fastapi import APIRouter

router = APIRouter()


@router.post("/requests")
def create_request(patient_id, text=None, audio=None):
    raise NotImplementedError
