"""Database leased jobs survive phone disconnects and API restarts."""
import base64
import logging
import threading
from datetime import timedelta
from uuid import UUID
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session
from app.db.models import Workspace, WorkspaceJob, WorkspaceChunk
from app.services import workspaces as ws

log = logging.getLogger(__name__)


def claim(session):
    job = session.scalar(select(WorkspaceJob).where(or_(WorkspaceJob.status == 'queued', (WorkspaceJob.status == 'running') & (WorkspaceJob.lease_until < ws.now()))).order_by(WorkspaceJob.created_at).with_for_update(skip_locked=True).limit(1))
    if job is None:
        return None
    job.attempts += 1
    job.status = 'running'
    job.lease_until = ws.now() + timedelta(minutes=15)
    ws.event(session, session.get(Workspace, job.workspace_id), 'running', job)
    return job.id


def execute(session, job):
    from app.mcp.workspace_tools import interpret_prompt, lookup_patient, open_workspace_views
    from app.agents.doctor import route_doctor_request, _research_answer
    w = session.get(Workspace, job.workspace_id)
    if job.attempts > 2:
        job.status = 'failed'
        ws.put(session, job.id, 'result', {'error': 'Processing was interrupted. Please send this request again.'})
        ws.event(session, w, 'failed', job)
        return
    if job.channel == 'voice' and not job.transcript:
        from app.speech.hook import SpeechHook
        raw = ws.read(session, job.id, 'audio')
        job.transcript = SpeechHook().transcribe(base64.b64decode(raw)).strip()
        if not job.transcript:
            raise ValueError('No speech was recognized. Try again or type your prompt.')
        if len(job.transcript.encode()) > 5500:
            raise ValueError('Dictation is too long. Send a shorter request.')
    if ws.read(session, job.id, 'clarification_voice', False):
        from app.speech.hook import SpeechHook
        query = SpeechHook().transcribe(base64.b64decode(ws.read(session, job.id, 'clarification_audio'))).strip()
        if not query:
            raise ValueError('No patient name was recognized. Please type the name.')
        ws.put(session, job.id, 'patient_query', query[:200])
        ws.put(session, job.id, 'clarification_voice', False)
        session.execute(delete(WorkspaceChunk).where(WorkspaceChunk.owner_id == job.id, WorkspaceChunk.slot == 'clarification_audio'))
    intent = ws.read(session, job.id, 'intent') or interpret_prompt(job.transcript, has_patient=bool(job.patient_id))
    explicit_route = ws.read(session, job.id, 'input', {}).get('route')
    if explicit_route and not (intent['views'] and intent['route'] is None):
        intent['route'] = explicit_route
        intent['needs_patient'] = explicit_route != 'clinical_question' or intent['needs_patient']
    intent['needs_patient'] = intent['needs_patient'] or bool(intent['views']) or intent['route'] in ('chart_update', 'check_screenings')
    ws.put(session, job.id, 'intent', intent)
    query = ws.read(session, job.id, 'patient_query') or intent.get('patient_query')
    resolved = ws.read(session, job.id, 'resolved', False)
    if query and not resolved:
        result = lookup_patient(query, session=session)
        candidates = result['patients']
        if len(candidates) == 1 and not result['has_more']:
            job.patient_id = UUID(candidates[0]['id'])
        else:
            job.patient_id = None
            job.status = 'needs_patient'
            ws.put(session, job.id, 'result', {'question': 'Which patient did you mean?' if candidates else 'I could not find that patient. What is their name or record ID?', 'candidates': candidates})
            ws.event(session, w, 'needs_patient', job)
            return
    elif not job.patient_id and intent['needs_patient']:
        job.status = 'needs_patient'
        ws.put(session, job.id, 'result', {'question': 'Which patient is this for?', 'candidates': []})
        ws.event(session, w, 'needs_patient', job)
        return
    if not intent['needs_patient'] and not query:
        job.patient_id = None
    navigation = open_workspace_views(job.patient_id, intent['views'], session=session) if intent['views'] else []
    if intent['route']:
        if job.patient_id:
            response = route_doctor_request(str(job.patient_id), job.transcript, job.channel, session=session, route=intent['route'])
        else:
            response = {'request_id': str(job.id), 'transcript': job.transcript, 'route': 'clinical_question', 'answer': _research_answer(None, job.transcript, None), 'suggestions': [], 'audio_base64': None, 'spoken_text': None}
        if 'error' in response:
            raise ValueError(response['error']['message'])
    else:
        response = {'request_id': str(job.id), 'transcript': job.transcript, 'route': 'navigate', 'answer': None, 'suggestions': [], 'audio_base64': None, 'spoken_text': None}
    if job.patient_id:
        session.refresh(w, with_for_update=True)
        w.patient_id = job.patient_id
    ws.put(session, job.id, 'result', {'response': response, 'navigation': navigation})
    session.execute(delete(WorkspaceChunk).where(WorkspaceChunk.owner_id == job.id, WorkspaceChunk.slot == 'audio'))
    job.status = 'completed'
    job.lease_until = None
    ws.event(session, w, 'completed', job)


def start_worker(engine):
    stop = threading.Event()
    def loop():
        while not stop.is_set():
            job_id = None
            try:
                with Session(engine) as session, session.begin():
                    job_id = claim(session)
                if job_id:
                    with Session(engine) as session, session.begin():
                        job = session.scalar(select(WorkspaceJob).where(WorkspaceJob.id == job_id).with_for_update())
                        execute(session, job)
            except Exception as exc:
                log.warning('Workspace job processing failed (%s)', type(exc).__name__)
                if job_id:
                    try:
                        with Session(engine) as session, session.begin():
                            job = session.get(WorkspaceJob, job_id)
                            job.status = 'failed'
                            job.lease_until = None
                            from app.integrations import IntegrationError
                            message = str(exc) if isinstance(exc, (IntegrationError, ValueError)) else 'This request could not finish. Try again; no chart changes were approved.'
                            ws.put(session, job.id, 'result', {'error': message})
                            ws.event(session, session.get(Workspace, job.workspace_id), 'failed', job)
                    except Exception:
                        log.exception('Could not record workspace job failure')
            stop.wait(1 if not job_id else 0.1)
    for index in range(2):
        thread = threading.Thread(target=loop, name=f'workspace-jobs-{index}', daemon=True)
        thread.start()
    return stop
