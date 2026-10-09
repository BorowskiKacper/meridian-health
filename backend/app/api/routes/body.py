from fastapi import APIRouter

router = APIRouter()


@router.get("/patients/{patient_id}/body-state")
def get_body_state(patient_id, specialty):
    raise NotImplementedError


@router.get("/patients/{patient_id}/regions/{region_key}")
def get_region(patient_id, region_key):
    raise NotImplementedError
