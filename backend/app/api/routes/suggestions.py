from fastapi import APIRouter
from pydantic import BaseModel

from app.api.errors import finish

router = APIRouter()


class PlanItemBody(BaseModel):
    patient_id: str
    request_id: str | None = None
    text: str
    citations: list


class ApproveBody(BaseModel):
    suggestion_ids: list[str]
    edits: dict | None = None


class RejectBody(BaseModel):
    suggestion_ids: list[str]
    reason: str


@router.get("/suggestions")
def list_suggestions(patient_id: str, status: str | None = None):
    import app.api.db as api_db
    import app.services.approval as approval

    with api_db.get_session() as session:
        result = approval.list_suggestions(patient_id, status, session=session)
        return finish(result)


@router.post("/suggestions")
def create_suggestion(body: PlanItemBody):
    import app.api.db as api_db
    import app.services.approval as approval

    with api_db.get_session() as session:
        result = approval.create_plan_item(
            body.patient_id,
            body.request_id,
            body.text,
            body.citations,
            session=session,
        )
        return finish(result)


@router.post("/suggestions/approve")
def approve(body: ApproveBody):
    import app.api.db as api_db
    import app.services.approval as approval

    with api_db.get_session() as session:
        result = approval.approve_suggestions(
            body.suggestion_ids,
            body.edits,
            session=session,
        )
        return finish(result)


@router.post("/suggestions/reject")
def reject(body: RejectBody):
    import app.api.db as api_db
    import app.services.approval as approval

    with api_db.get_session() as session:
        result = approval.reject_suggestions(
            body.suggestion_ids,
            body.reason,
            session=session,
        )
        return finish(result)
