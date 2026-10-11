"""Durable paired-device workspaces. Pairing is revocable, never time-limited."""
import base64
import hashlib
import json
import secrets
import zlib
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select
from app.db.models import Workspace, WorkspaceJob, WorkspaceEvent, WorkspaceChunk, Patient, Suggestion


def now():
    return datetime.now(timezone.utc)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def put(session, owner, slot, value):
    session.execute(delete(WorkspaceChunk).where(WorkspaceChunk.owner_id == owner, WorkspaceChunk.slot == slot))
    encoded = base64.b64encode(zlib.compress(json.dumps(value, default=str).encode())).decode()
    for part, start in enumerate(range(0, len(encoded), 5000)):
        session.add(WorkspaceChunk(owner_id=owner, slot=slot, part=part, body=encoded[start:start + 5000]))
    session.flush()


def read(session, owner, slot, default=None):
    parts = session.scalars(select(WorkspaceChunk.body).where(WorkspaceChunk.owner_id == owner, WorkspaceChunk.slot == slot).order_by(WorkspaceChunk.part)).all()
    return json.loads(zlib.decompress(base64.b64decode(''.join(parts)))) if parts else default


def authorize(session, token, desktop=False):
    if not token or not token.startswith('Bearer '):
        raise HTTPException(401, 'Pair this device first.')
    hashed = digest(token[7:])
    w = session.scalar(select(Workspace).where(Workspace.desktop_hash == hashed))
    if w is not None:
        return w, 'desktop'
    if not desktop:
        w = session.scalar(select(Workspace).where(Workspace.phone_hash == hashed))
        if w is not None:
            return w, 'phone'
    raise HTTPException(401, 'This device was disconnected. Pair again.')


def event(session, w, kind, job=None):
    # Serialize event numbering, including across API workers.
    session.flush()
    session.refresh(w, with_for_update=True)
    w.sequence += 1
    session.add(WorkspaceEvent(id=uuid4(), workspace_id=w.id, sequence=w.sequence, kind=kind, job_id=job.id if job else None))
    session.flush()


def create(session):
    token = secrets.token_urlsafe(32)
    w = Workspace(id=uuid4(), desktop_hash=digest(token), phone_hash=None, code_hash=None, code_expires_at=None, patient_id=None, sequence=0, desktop_cursor=0, created_at=now())
    session.add(w)
    session.flush()
    return {'workspace_id': str(w.id), 'token': token}


def pairing_code(session, w):
    session.refresh(w, with_for_update=True)
    code = secrets.token_hex(4).upper()
    w.code_hash = digest(code)
    w.code_expires_at = now() + timedelta(minutes=5)
    return {'code': code, 'expires_at': w.code_expires_at}


def pair(session, code):
    code = code.strip().replace('-', '').replace(' ', '').upper()
    w = session.scalar(select(Workspace).where(Workspace.code_hash == digest(code)).with_for_update())
    if w is None or w.code_expires_at < now():
        raise HTTPException(400, 'This pairing code is invalid or expired. Generate another on your laptop.')
    if w.phone_hash:
        raise HTTPException(409, 'Disconnect the existing phone before pairing another.')
    token = secrets.token_urlsafe(32)
    w.phone_hash = digest(token)
    w.code_hash = None
    w.code_expires_at = None
    event(session, w, 'paired')
    return {'workspace_id': str(w.id), 'token': token}


def job_data(session, job, w):
    return jobs_data(session, [job], w)[0]


def jobs_data(session, jobs, w):
    """Batch poll reads instead of fetching results, patients and proposals per job."""
    if not jobs:
        return []
    chunks = session.scalars(select(WorkspaceChunk).where(WorkspaceChunk.owner_id.in_([j.id for j in jobs]), WorkspaceChunk.slot.in_(['result', 'desktop_delivery'])).order_by(WorkspaceChunk.part)).all()
    grouped = {}
    for chunk in chunks:
        grouped.setdefault((chunk.owner_id, chunk.slot), []).append(chunk.body)
    decoded = {key: json.loads(zlib.decompress(base64.b64decode(''.join(parts)))) for key, parts in grouped.items()}
    patient_ids = {j.patient_id for j in jobs if j.patient_id}
    patients = dict(session.execute(select(Patient.id, Patient.display_name).where(Patient.id.in_(patient_ids))).all()) if patient_ids else {}
    proposal_ids = {UUID(p['id']) for j in jobs for p in decoded.get((j.id, 'result'), {}).get('response', {}).get('suggestions', [])}
    statuses = dict(session.execute(select(Suggestion.id, Suggestion.status).where(Suggestion.id.in_(proposal_ids))).all()) if proposal_ids else {}
    result = []
    for job in jobs:
        data = decoded.get((job.id, 'result'), {})
        for proposal in data.get('response', {}).get('suggestions', []):
            proposal['status'] = statuses.get(UUID(proposal['id']), proposal['status'])
        result.append({'id': str(job.id), 'status': job.status, 'text': job.transcript, 'patient_id': str(job.patient_id) if job.patient_id else None,
                       'patient_name': patients.get(job.patient_id), 'channel': job.channel, 'created_at': job.created_at,
                       **data, 'desktop_applied': bool(decoded.get((job.id, 'desktop_delivery'), False))})
    return result


def submit(session, w, submission_id, text, audio=None, patient_id=None, route=None):
    session.refresh(w, with_for_update=True)
    payload = {'text': text, 'audio_hash': hashlib.sha256(audio).hexdigest() if audio else None, 'patient_id': str(patient_id) if patient_id else None, 'route': route}
    existing = session.get(WorkspaceJob, submission_id)
    if existing:
        if existing.workspace_id != w.id or read(session, existing.id, 'input') != payload:
            raise HTTPException(409, 'Submission already used for a different request.')
        return job_data(session, existing, w)
    if patient_id and session.get(Patient, patient_id) is None:
        raise HTTPException(404, 'Patient not found.')
    if len(text.encode()) > 5500:
        raise HTTPException(400, 'Shorten this prompt before sending.')
    job = WorkspaceJob(id=submission_id, workspace_id=w.id, patient_id=patient_id, transcript=text, status='queued', channel='voice' if audio else 'typed', attempts=0, lease_until=None, created_at=now())
    session.add(job)
    session.flush()
    put(session, job.id, 'input', payload)
    if audio:
        put(session, job.id, 'audio', base64.b64encode(audio).decode())
    event(session, w, 'queued', job)
    if not audio:
        from app.mcp.workspace_tools import parse_navigation
        intent = parse_navigation(text)
        if intent is not None:
            # No provider calls or clinical writes: navigation need not wait behind research.
            from app.services.workspace_worker import execute
            put(session, job.id, 'intent', intent)
            execute(session, job)
    return job_data(session, job, w)


def clarify(session, w, job_id, text='', patient_id=None):
    session.refresh(w, with_for_update=True)
    job = session.get(WorkspaceJob, job_id)
    if not job or job.workspace_id != w.id:
        raise HTTPException(404, 'Request not found.')
    if job.status != 'needs_patient':
        raise HTTPException(409, 'This request is no longer waiting for a patient.')
    if patient_id:
        choices = read(session, job.id, 'result', {}).get('candidates', [])
        if str(patient_id) not in {p['id'] for p in choices}:
            raise HTTPException(400, 'Choose a patient from the current matches.')
        job.patient_id = patient_id
        put(session, job.id, 'resolved', True)
    else:
        put(session, job.id, 'patient_query', text.strip())
    job.status = 'queued'
    job.attempts = 0
    event(session, w, 'queued', job)
    return job_data(session, job, w)
