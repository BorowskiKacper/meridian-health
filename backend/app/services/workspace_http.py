"""Workspace read models, snapshots and scoped chart review."""
import base64
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from app.db.models import WorkspaceJob, WorkspaceEvent, Patient
from app.services import workspaces as ws


def state(session, w, device, after):
    events = session.scalars(select(WorkspaceEvent).where(WorkspaceEvent.workspace_id == w.id, WorkspaceEvent.sequence > after).order_by(WorkspaceEvent.sequence).limit(50)).all()
    jobs = session.scalars(select(WorkspaceJob).where(WorkspaceJob.workspace_id == w.id).order_by(WorkspaceJob.created_at.desc()).limit(100)).all()
    patient = session.get(Patient, w.patient_id) if w.patient_id else None
    return {'paired': bool(w.phone_hash), 'patient_name': patient.display_name if patient else None, 'workspace_id': str(w.id), 'cursor': events[-1].sequence if events else after,
            'events': [{'sequence': e.sequence, 'kind': e.kind, 'job_id': str(e.job_id) if e.job_id else None} for e in events],
            'jobs': [ws.job_data(session, j, w) for j in reversed(jobs)],
            'snapshot': ws.read(session, w.id, 'snapshot') if device == 'desktop' else None}


def snapshot(session, w, payload):
    from app.mcp.workspace_tools import open_workspace_views
    session.refresh(w, with_for_update=True)
    if payload.cursor < w.desktop_cursor or payload.cursor > w.sequence:
        raise HTTPException(409, 'Workspace changed. Reload the current state.')
    for tab in payload.tabs:
        if not isinstance(tab.get('id'), str) or len(tab['id']) > 150:
            raise HTTPException(400, 'Invalid tab.')
        if tab.get('kind') not in ('region', 'research'):
            try:
                open_workspace_views(tab.get('patientId'), [tab.get('kind')], session=session)
            except (ValueError, TypeError):
                raise HTTPException(400, 'Unsupported chart view.')
        elif tab.get('kind') == 'research':
            try:
                job = session.get(WorkspaceJob, UUID(tab.get('refId', '')))
            except (ValueError, TypeError):
                raise HTTPException(400, 'Invalid research reference.')
            if not job or job.workspace_id != w.id or job.status != 'completed':
                raise HTTPException(400, 'Research result not found in this workspace.')
        else:
            try:
                patient = session.get(Patient, UUID(tab.get('patientId', '')))
            except (ValueError, TypeError):
                raise HTTPException(400, 'Invalid patient identifier.')
            if patient is None:
                raise HTTPException(400, 'Patient not found.')
    if payload.activeTabId is not None and not any(t['id'] == payload.activeTabId for t in payload.tabs):
        raise HTTPException(400, 'Active tab is not in this workspace.')
    ws.put(session, w.id, 'snapshot', payload.model_dump())
    w.desktop_cursor = payload.cursor
    return {'saved': True}


def disconnect(session, w):
    session.refresh(w, with_for_update=True)
    w.phone_hash = w.code_hash = None
    ws.event(session, w, 'disconnected')
    return {'disconnected': True}


def get_job(session, w, job_id):
    job = session.get(WorkspaceJob, job_id)
    if not job or job.workspace_id != w.id:
        raise HTTPException(404, 'Request not found.')
    return ws.job_data(session, job, w)


def clarify_voice(session, w, job_id, raw):
    session.refresh(w, with_for_update=True)
    job = session.get(WorkspaceJob, job_id)
    if not job or job.workspace_id != w.id:
        raise HTTPException(404, 'Request not found.')
    if job.status != 'needs_patient':
        raise HTTPException(409, 'This request is no longer waiting for a patient.')
    ws.put(session, job.id, 'clarification_audio', base64.b64encode(raw).decode())
    ws.put(session, job.id, 'clarification_voice', True)
    job.status = 'queued'
    job.attempts = 0
    ws.event(session, w, 'queued', job)
    return ws.job_data(session, job, w)


def review(session, w, payload, approve):
    from app.services.approval import approve_suggestions, reject_suggestions
    jobs = session.scalars(select(WorkspaceJob).where(WorkspaceJob.workspace_id == w.id, WorkspaceJob.status == 'completed')).all()
    allowed = {p['id'] for j in jobs for p in ws.read(session, j.id, 'result', {}).get('response', {}).get('suggestions', [])}
    ids = [str(i) for i in payload.suggestion_ids]
    if not set(ids) <= allowed:
        raise HTTPException(404, 'Proposal not found in this workspace.')
    result = approve_suggestions(ids, None, session=session) if approve else reject_suggestions(ids, payload.reason, session=session)
    if 'error' not in result:
        ws.event(session, w, 'chart_changed')
    return result
