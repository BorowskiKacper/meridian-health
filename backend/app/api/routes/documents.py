from fastapi import APIRouter

router = APIRouter()


@router.post("/documents")
def upload_document(patient_id, file, media_type):
    raise NotImplementedError
