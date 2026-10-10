from fastapi import APIRouter
from pydantic import BaseModel

from app.api.errors import finish

router = APIRouter()


class EligibilityBody(BaseModel):
    order_text: str | None = None


@router.post("/patients/{patient_id}/eligibility")
def check_eligibility(patient_id: str, body: EligibilityBody):
    import app.api.db as api_db
    import app.services.eligibility as eligibility

    with api_db.get_session() as session:
        result = eligibility.check_eligibility(
            patient_id,
            body.order_text,
            session=session,
        )
        return finish(result)
