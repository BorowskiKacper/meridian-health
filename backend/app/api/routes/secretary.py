from typing import Annotated

from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.api.errors import finish, reject_unless_secretary

router = APIRouter()


class SecretaryRequest(BaseModel):
    patient_id: str
    text: str


@router.post("/secretary/requests")
def create_secretary_request(
    body: SecretaryRequest,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
):
    denied = reject_unless_secretary(x_role)
    if denied is not None:
        return denied
    import app.api.db as api_db
    import app.agents.secretary as secretary

    with api_db.get_session() as session:
        result = secretary.answer_secretary(body.patient_id, body.text, session=session)
        return finish(result)
