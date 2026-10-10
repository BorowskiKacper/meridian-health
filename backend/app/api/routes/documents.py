from fastapi import APIRouter, File, Form, UploadFile

from app.api.errors import finish

router = APIRouter()


@router.post("/documents")
async def upload_document(
    patient_id: str = Form(...),
    file: UploadFile = File(...),
):
    import app.api.db as api_db
    import app.services.labs as labs

    session = api_db.get_session()
    content = await file.read()
    result = labs.extract_lab_report(
        patient_id,
        content,
        file.content_type,
        session=session,
    )
    return finish(result)
