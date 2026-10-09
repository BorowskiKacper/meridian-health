from fastapi import APIRouter

router = APIRouter()


@router.get("/suggestions")
def list_suggestions(patient_id, status="pending"):
    raise NotImplementedError


@router.post("/suggestions")
def create_suggestion(patient_id, request_id, text, citations):
    raise NotImplementedError


@router.post("/suggestions/approve")
def approve(suggestion_ids, edits=None):
    raise NotImplementedError


@router.post("/suggestions/reject")
def reject(suggestion_ids, reason):
    raise NotImplementedError
