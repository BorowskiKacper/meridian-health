"""Paired-device lifecycle and durable requests, without external providers."""
from datetime import timedelta
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from api_support import AMY_ID, JANE_ID, bind_session
from app.db.models import Workspace, WorkspaceJob, Note, Suggestion
from app.services import workspaces as ws
from app.services.workspace_worker import claim, execute


@pytest.fixture
def paired(client, seeded_db, monkeypatch):
    from app.api.routes.workspaces import _attempts
    _attempts.clear()
    bind_session(monkeypatch, seeded_db.session)
    created = client.post('/workspaces').json()
    desktop = {'Authorization': 'Bearer ' + created['token']}
    code = client.post('/workspaces/pairing-code', headers=desktop).json()['code']
    response = client.post('/workspaces/pair', json={'code': code})
    assert response.status_code == 200
    phone = {'Authorization': 'Bearer ' + response.json()['token']}
    seeded_db.session.commit()
    return desktop, phone, code, seeded_db.session


def submit(client, headers, text='Open Amy Lee’s trends', **data):
    response = client.post('/workspaces/requests', headers=headers, data={'submission_id': str(uuid4()), 'text': text, **data})
    assert response.status_code == 202, response.text
    return response.json()


def run(session, monkeypatch, *, query='Amy Lee', views=None, route=None, needs=True):
    import app.mcp.workspace_tools as tools
    monkeypatch.setattr(tools, 'interpret_prompt', lambda *args, **kwargs: {'patient_query': query, 'needs_patient': needs, 'views': ['vitals'] if views is None else views, 'route': route})
    job_id = claim(session)
    session.commit()
    execute(session, session.get(WorkspaceJob, job_id))
    session.commit()
    return job_id


def test_pairing_persists_until_revoked_and_code_is_single_use(client, paired):
    desktop, phone, code, session = paired
    assert client.post('/workspaces/pair', json={'code': code}).status_code == 400
    w = session.scalar(select(Workspace))
    w.created_at = ws.now() - timedelta(days=365)
    session.commit()
    assert client.get('/workspaces/state', headers=phone).status_code == 200
    assert client.get('/workspaces/state').status_code == 401
    assert client.post('/workspaces/pairing-code', headers=phone).status_code == 401
    assert client.post('/workspaces/disconnect', headers=desktop).status_code == 200
    session.commit()
    assert client.get('/workspaces/state', headers=phone).status_code == 401
    assert client.get('/workspaces/state', headers=desktop).status_code == 200


def test_pairing_code_expires_not_device(client, seeded_db, monkeypatch):
    from app.api.routes.workspaces import _attempts
    _attempts.clear()
    bind_session(monkeypatch, seeded_db.session)
    token = client.post('/workspaces').json()['token']
    code = client.post('/workspaces/pairing-code', headers={'Authorization': 'Bearer ' + token}).json()['code']
    w = seeded_db.session.scalar(select(Workspace))
    w.code_expires_at = ws.now() - timedelta(seconds=1)
    seeded_db.session.commit()
    assert client.post('/workspaces/pair', json={'code': code}).status_code == 400


def test_navigation_is_durable_scoped_and_acknowledged_only_after_snapshot(client, paired, monkeypatch):
    desktop, phone, _, session = paired
    job = submit(client, phone)
    session.commit()
    assert job['status'] == 'queued'
    run(session, monkeypatch)
    state = client.get('/workspaces/state', headers=desktop).json()
    done = state['jobs'][0]
    assert done['navigation'] == [{'patient_id': AMY_ID, 'view': 'vitals'}]
    assert not done['desktop_applied']
    snapshot = {'cursor': state['cursor'], 'tabs': [{'id': 'vitals-amy', 'kind': 'vitals', 'patientId': AMY_ID}], 'activeTabId': 'vitals-amy'}
    assert client.put('/workspaces/snapshot', headers=desktop, json=snapshot).status_code == 200
    session.commit()
    reloaded = client.get('/workspaces/state', headers=desktop).json()
    assert reloaded['snapshot'] == snapshot
    assert reloaded['jobs'][0]['desktop_applied']
    # Closing a tab retains the cursor, so replay cannot reopen it.
    assert client.put('/workspaces/snapshot', headers=desktop, json={**snapshot, 'tabs': [], 'activeTabId': None}).status_code == 200
    session.commit()
    assert client.get(f"/workspaces/state?after={state['cursor']}", headers=desktop).json()['events'] == []
    assert client.put('/workspaces/snapshot', headers=phone, json=snapshot).status_code == 401
    other = client.post('/workspaces').json()['token']
    assert client.get('/workspaces/requests/' + job['id'], headers={'Authorization': 'Bearer ' + other}).status_code == 404


def test_missing_patient_clarification_preserves_original_request(client, paired, monkeypatch):
    desktop, phone, _, session = paired
    job = submit(client, phone, 'Open the medication list')
    session.commit()
    run(session, monkeypatch, query=None, views=['medications'])
    waiting = client.get('/workspaces/requests/' + job['id'], headers=phone).json()
    assert waiting['status'] == 'needs_patient'
    assert client.post('/workspaces/requests/' + job['id'] + '/clarify', headers=phone, json={'text': 'Amy Lee'}).status_code == 200
    session.commit()
    run(session, monkeypatch, query=None, views=['medications'])
    done = client.get('/workspaces/requests/' + job['id'], headers=desktop).json()
    assert done['text'] == 'Open the medication list'
    assert done['patient_id'] == AMY_ID
    assert done['navigation'][0]['view'] == 'medications'


def test_ambiguous_patient_never_uses_previous_patient(client, paired, monkeypatch):
    from app.db.models import Patient
    desktop, phone, _, session = paired
    w = session.scalar(select(Workspace))
    w.patient_id = UUID(AMY_ID)
    session.add(Patient(id=uuid4(), display_name='Amy Smith', date_of_birth=__import__('datetime').date(1990, 1, 1), sex='F', email_opt_in=False, email=''))
    session.commit()
    job = submit(client, phone, 'Open Amy’s trends')
    session.commit()
    run(session, monkeypatch, query='Amy')
    waiting = client.get('/workspaces/requests/' + job['id'], headers=phone).json()
    assert waiting['status'] == 'needs_patient' and waiting['patient_id'] is None
    assert len(waiting['candidates']) == 2
    path = '/workspaces/requests/' + job['id'] + '/clarify'
    assert client.post(path, headers=phone, json={'patient_id': JANE_ID}).status_code == 400
    assert client.post(path, headers=phone, json={'patient_id': AMY_ID}).status_code == 200
    session.commit()
    run(session, monkeypatch, query='Amy')
    assert client.get('/workspaces/requests/' + job['id'], headers=phone).json()['patient_id'] == AMY_ID


def test_idempotent_submission_and_restart_claim(client, paired, monkeypatch):
    desktop, phone, _, session = paired
    data = {'submission_id': str(uuid4()), 'text': 'Open Amy Lee trends'}
    first = client.post('/workspaces/requests', headers=phone, data=data)
    session.commit()
    second = client.post('/workspaces/requests', headers=phone, data=data)
    assert first.json()['id'] == second.json()['id']
    assert client.post('/workspaces/requests', headers=phone, data={**data, 'text': 'Different'}).status_code == 409
    job_id = claim(session)
    session.commit()
    job = session.get(WorkspaceJob, job_id)
    job.lease_until = ws.now() - timedelta(seconds=1)
    session.commit()
    assert run(session, monkeypatch) == job_id
    assert session.get(WorkspaceJob, job_id).status == 'completed'
    assert claim(session) is None


def test_research_is_saved_with_citations_and_no_record_writes(client, paired, monkeypatch):
    import app.agents.doctor as doctor
    desktop, phone, _, session = paired
    before = len(session.scalars(select(Note)).all())
    monkeypatch.setattr(doctor, '_research_answer', lambda *args: {'text': 'Evidence answer', 'citations': [{'title': 'Study', 'source_id': 'study', 'locator': 'https://pubmed.ncbi.nlm.nih.gov/1/', 'passage': 'Evidence', 'tier': 'literature'}]})
    job = submit(client, phone, 'Explain hypertension guidelines generally')
    session.commit()
    run(session, monkeypatch, query=None, views=[], route='clinical_question', needs=False)
    done = client.get('/workspaces/requests/' + job['id'], headers=desktop).json()
    assert done['response']['answer']['citations'][0]['title'] == 'Study'
    assert done['patient_id'] is None
    assert len(session.scalars(select(Note)).all()) == before


def test_large_saved_results_use_bounded_chunks(paired):
    import hashlib
    from app.db.models import WorkspaceChunk
    _, _, _, session = paired
    w = session.scalar(select(Workspace))
    payload = {'answer': ''.join(hashlib.sha256(str(i).encode()).hexdigest() for i in range(2000))}
    ws.put(session, w.id, 'test', payload)
    session.commit()
    assert ws.read(session, w.id, 'test') == payload
    assert len(session.scalars(select(WorkspaceChunk).where(WorkspaceChunk.slot == 'test')).all()) > 1


def test_prior_workspace_patient_is_not_an_implicit_prompt_target(client, paired, monkeypatch):
    _, phone, _, session = paired
    session.scalar(select(Workspace)).patient_id = UUID(AMY_ID)
    session.commit()
    job = submit(client, phone, 'Open the problem list')
    session.commit()
    run(session, monkeypatch, query=None, views=['problems'])
    result = client.get('/workspaces/requests/' + job['id'], headers=phone).json()
    assert result['status'] == 'needs_patient'
    assert result['patient_id'] is None


def test_navigation_does_not_become_research_from_desktop_mode(client, paired, monkeypatch):
    _, phone, _, session = paired
    job = submit(client, phone, 'Open Amy Lee vitals', route='clinical_question')
    session.commit()
    run(session, monkeypatch)
    result = client.get('/workspaces/requests/' + job['id'], headers=phone).json()
    assert result['response']['route'] == 'navigate'
    assert result['response']['suggestions'] == []


def test_phone_approval_updates_desktop_result_and_enforces_workspace_scope(client, paired, monkeypatch):
    import app.agents.doctor as doctor
    from app.db.models import Condition
    from app.db.repositories import insert_suggestion
    desktop, phone, _, session = paired
    target = session.scalar(select(Condition).where(Condition.patient_id == UUID(JANE_ID), Condition.name == 'Hypertension'))
    def response(*args, **kwargs):
        proposal = insert_suggestion(session, {'id': str(uuid4()), 'patient_id': JANE_ID, 'request_id': None, 'kind': 'field_update', 'status': 'pending', 'target_table': 'conditions', 'target_id': str(target.id), 'before': {'status': target.status}, 'after': {'status': 'resolved'}, 'reason': 'Clinician requested status update', 'confidence': 0.9, 'citations': [], 'validation_flags': [], 'source': 'chart_agent'})
        return {'request_id': str(uuid4()), 'transcript': 'Resolve problem', 'route': 'chart_update', 'answer': None, 'suggestions': [proposal], 'spoken_text': None, 'audio_base64': None}
    monkeypatch.setattr(doctor, 'route_doctor_request', response)
    job = submit(client, phone, 'Resolve the recorded problem for Jane Doe')
    session.commit()
    run(session, monkeypatch, query='Jane Doe', views=[], route='chart_update')
    result = client.get('/workspaces/requests/' + job['id'], headers=phone).json()
    proposal = result['response']['suggestions'][0]['id']
    assert target.status == 'active'
    assert client.post('/workspaces/approve', headers=phone, json={'suggestion_ids': [str(uuid4())]}).status_code == 404
    assert client.post('/workspaces/approve', headers=phone, json={'suggestion_ids': [proposal]}).status_code == 200
    session.commit()
    updated = client.get('/workspaces/requests/' + job['id'], headers=desktop).json()
    assert updated['response']['suggestions'][0]['status'] == 'approved'
    assert session.get(Condition, target.id).status == 'resolved'
    assert any(e['kind'] == 'chart_changed' for e in client.get('/workspaces/state', headers=desktop).json()['events'])
    assert client.post('/workspaces/reject', headers=phone, json={'suggestion_ids': [proposal]}).status_code == 409


def test_voice_patient_clarification_keeps_original_prompt(client, paired, monkeypatch):
    from app.speech.hook import SpeechHook
    _, phone, _, session = paired
    job = submit(client, phone, 'Open the allergies')
    session.commit()
    run(session, monkeypatch, query=None, views=['allergies'])
    monkeypatch.setattr(SpeechHook, 'transcribe', lambda *args: 'Amy Lee')
    response = client.post('/workspaces/requests/' + job['id'] + '/clarify-voice', headers=phone, files={'audio': ('patient.m4a', b'fake audio', 'audio/mp4')})
    assert response.status_code == 200
    session.commit()
    run(session, monkeypatch, query=None, views=['allergies'])
    result = client.get('/workspaces/requests/' + job['id'], headers=phone).json()
    assert result['text'] == 'Open the allergies'
    assert result['patient_id'] == AMY_ID
