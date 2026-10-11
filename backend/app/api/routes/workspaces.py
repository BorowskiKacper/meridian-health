"""Bearer-scoped APIs for paired mobile and desktop workspaces."""
from collections import defaultdict, deque
import time
from uuid import UUID
from fastapi import APIRouter, Header, HTTPException, Request, Query
from pydantic import BaseModel, Field
from app.api import db
from app.api.errors import finish
from app.services import workspace_http as views
from app.services import workspaces as ws

router = APIRouter(prefix='/workspaces', tags=['workspace'])
_attempts = defaultdict(deque)


def limited(request, action):
    key = (request.client.host if request.client else 'unknown', action)
    times = _attempts[key]
    while times and times[0] < time.monotonic() - 60:
        times.popleft()
    if len(times) >= 10:
        raise HTTPException(429, 'Too many attempts. Please wait a minute.')
    times.append(time.monotonic())


class Pair(BaseModel):
    code: str = Field(min_length=1, max_length=30)


class Clarify(BaseModel):
    text: str = Field(default='', max_length=200)
    patient_id: UUID | None = None


class Snapshot(BaseModel):
    cursor: int = Field(ge=0)
    tabs: list[dict] = Field(max_length=80)
    activeTabId: str | None = None


class Review(BaseModel):
    suggestion_ids: list[UUID] = Field(min_length=1, max_length=30)
    reason: str = Field(default='Not accurate', max_length=1000)


@router.post('')
def create_workspace(request: Request):
    limited(request, 'create')
    with db.get_session() as session:
        return ws.create(session)


@router.post('/pair')
def pair(request: Request, payload: Pair):
    limited(request, 'pair')
    with db.get_session() as session:
        return ws.pair(session, payload.code)


@router.post('/pairing-code')
def code(authorization: str | None = Header(default=None)):
    with db.get_session() as session:
        w, _ = ws.authorize(session, authorization, desktop=True)
        return ws.pairing_code(session, w)


@router.post('/disconnect')
def disconnect(authorization: str | None = Header(default=None)):
    with db.get_session() as session:
        w, _ = ws.authorize(session, authorization)
        return views.disconnect(session, w)


@router.get('/state')
def state(after: int = Query(default=0, ge=0), authorization: str | None = Header(default=None)):
    with db.get_session() as session:
        w, device = ws.authorize(session, authorization)
        return views.state(session, w, device, after)


@router.put('/snapshot')
def snapshot(payload: Snapshot, authorization: str | None = Header(default=None)):
    with db.get_session() as session:
        w, _ = ws.authorize(session, authorization, desktop=True)
        return views.snapshot(session, w, payload)


@router.post('/requests', status_code=202)
async def submit(request: Request, authorization: str | None = Header(default=None)):
    # Authenticate before accepting or reading uploads.
    with db.get_session() as session:
        w, _ = ws.authorize(session, authorization)
        form = await request.form()
        from starlette.datastructures import UploadFile
        text, audio = form.get('text'), form.get('audio')
        if isinstance(text, str) == isinstance(audio, UploadFile):
            raise HTTPException(400, 'Send exactly one of text or audio.')
        try:
            submission_id = UUID(form.get('submission_id', ''))
            patient_id = UUID(form['patient_id']) if form.get('patient_id') else None
        except (ValueError, TypeError):
            raise HTTPException(400, 'Invalid request identifier.')
        raw = await audio.read(10 * 1024 * 1024 + 1) if isinstance(audio, UploadFile) else None
        if raw is not None and (not raw or len(raw) > 10 * 1024 * 1024):
            raise HTTPException(400, 'Recording must be nonempty and smaller than 10 MB.')
        text = text.strip() if isinstance(text, str) else ''
        if raw is None and not text:
            raise HTTPException(400, 'Enter a prompt.')
        route = form.get('route')
        if route not in (None, 'chart_update', 'clinical_question', 'check_screenings'):
            raise HTTPException(400, 'Unknown workflow.')
        return ws.submit(session, w, submission_id, text, raw, patient_id, route)


@router.post('/requests/{job_id}/clarify')
def clarify(job_id: UUID, payload: Clarify, authorization: str | None = Header(default=None)):
    if not payload.patient_id and not payload.text.strip():
        raise HTTPException(400, 'Enter a patient name or choose a match.')
    with db.get_session() as session:
        w, _ = ws.authorize(session, authorization)
        return ws.clarify(session, w, job_id, payload.text, payload.patient_id)


@router.get('/requests/{job_id}')
def get_job(job_id: UUID, authorization: str | None = Header(default=None)):
    with db.get_session() as session:
        w, _ = ws.authorize(session, authorization)
        return views.get_job(session, w, job_id)


@router.post('/requests/{job_id}/clarify-voice')
async def clarify_voice(job_id: UUID, request: Request, authorization: str | None = Header(default=None)):
    from starlette.datastructures import UploadFile
    with db.get_session() as session:
        w, _ = ws.authorize(session, authorization)
        form = await request.form()
        audio = form.get('audio')
        if not isinstance(audio, UploadFile):
            raise HTTPException(400, 'Recording required.')
        raw = await audio.read(10 * 1024 * 1024 + 1)
        if not raw or len(raw) > 10 * 1024 * 1024:
            raise HTTPException(400, 'Recording must be nonempty and smaller than 10 MB.')
        return views.clarify_voice(session, w, job_id, raw)




@router.post('/approve')
def approve(payload: Review, authorization: str | None = Header(default=None)):
    with db.get_session() as session:
        w, _ = ws.authorize(session, authorization)
        return finish(views.review(session, w, payload, True))


@router.post('/reject')
def reject(payload: Review, authorization: str | None = Header(default=None)):
    with db.get_session() as session:
        w, _ = ws.authorize(session, authorization)
        return finish(views.review(session, w, payload, False))
