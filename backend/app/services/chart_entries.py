"""Transactional manual chart capture for the local clinic demo.

Patient review logs do not establish authenticated clinician identity.
"""
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid5
from sqlalchemy import select
from app.db.models import Allergy, AuditLog, BodyRegion, Condition, Medication, Observation, Patient, Reminder, Note
from app.schemas.chart_entries import Submission, Vitals, MedicationEntry, AllergyEntry, ProblemEntry, VisitDraft, Review, Inactivate, NoKnownDrugAllergies, FollowUp


def _error(code, message):
    return {"error": {"code": code, "message": message}}


def _snapshot(session, patient_id, kind):
    model = Medication if kind == 'medications' else Allergy
    rows = session.scalars(select(model).where(model.patient_id == patient_id).order_by(model.id)).all()
    return [{c.key: str(getattr(row, c.key)) for c in model.__table__.columns} for row in rows]


def _version(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def _save(patient_id, payload, action, write, *, session):
    # Serialize manual writes and retries across workers for the same patient.
    patient = session.scalar(select(Patient).where(Patient.id == patient_id).with_for_update())
    if patient is None:
        return _error('not_found', 'Patient not found.')
    content = payload.model_dump(mode='json', exclude={'submission_id'})
    if len(json.dumps(content).encode()) > 6000:
        return _error('validation_error', 'This demo supports entries up to 6 KB. Shorten the note and save again.')
    existing = session.get(AuditLog, payload.submission_id)
    if existing:
        receipt = json.loads(existing.detail)
        if existing.patient_id != patient_id or existing.action != action or receipt['input'] != content:
            return _error('invalid_state', 'This submission was already saved with different data. Reload before creating another entry.')
        return {'saved': True, 'id': str(existing.id), 'saved_at': existing.created_at}
    with session.begin_nested() as transaction:
        extra = write(session, content)
        if isinstance(extra, dict) and 'error' in extra:
            transaction.rollback()
            return extra
        detail = json.dumps({'input': content, **(extra or {})})
        # The demo's existing audit table stores text inline in a PostgreSQL row.
        if len(detail.encode()) > 7000:
            transaction.rollback()
            return _error('validation_error', "This entry exceeds the demo's storage limit. Shorten the text and save again.")
        now = datetime.now(timezone.utc)
        session.add(AuditLog(id=payload.submission_id, patient_id=patient_id, suggestion_id=None, action=action, detail=detail, created_at=now))
        session.flush()
    return {'saved': True, 'id': str(payload.submission_id), 'saved_at': now}


def record_vitals(patient_id: UUID, payload: Vitals, *, session):

    def write(session, content):
        for key, name, unit in [('systolic', 'Systolic blood pressure', 'mmHg'), ('diastolic', 'Diastolic blood pressure', 'mmHg'), ('weight_kg', 'Body weight', 'kg'), ('pulse', 'Heart rate', 'beats/min'), ('respiratory_rate', 'Respiratory rate', 'breaths/min'), ('temperature_f', 'Body temperature', '°F')]:
            if content[key] is not None:
                session.add(Observation(id=uuid5(payload.submission_id, key), patient_id=patient_id, name=name, value=content[key], unit=unit, observed_at=payload.observed_at, source='manual_entry', document_id=None, body_region_key='heart'))
    return _save(patient_id, payload, 'manual_vitals', write, session=session)


def _record(patient_id, payload, model, action, record_id=None, *, session):

    def write(session, content):
        if 'body_region_key' in content and session.get(BodyRegion, content['body_region_key']) is None:
            return _error('validation_error', 'Choose a recorded chart region.')
        if model is Allergy:
            nkda = session.scalar(select(Allergy).where(Allergy.patient_id == patient_id, Allergy.category == 'nkda', Allergy.status == 'active'))
            if nkda and content['category'] == 'drug' and (content['status'] == 'active'):
                return _error('invalid_state', 'An active no-known-drug-allergy record exists. Resolve that record before adding an active drug allergy.')
        row = session.get(model, record_id) if record_id else None
        if record_id and (row is None or row.patient_id != patient_id):
            return _error('not_found', 'Chart record not found for this patient.')
        before = {c.key: str(getattr(row, c.key)) for c in model.__table__.columns} if row else None
        values = payload.model_dump(exclude={'submission_id'})
        if row:
            for key, value in values.items():
                setattr(row, key, value)
        else:
            if model is Allergy:
                values['verified_by'] = 'manual_entry_unverified'
            session.add(model(id=uuid5(payload.submission_id, action), patient_id=patient_id, **values))
        return {'before': before, 'record_id': str(record_id) if record_id else str(uuid5(payload.submission_id, action))}
    return _save(patient_id, payload, f'{action}:{record_id}' if record_id else action, write, session=session)


def add_medication(patient_id: UUID, payload: MedicationEntry, *, session):
    return _record(patient_id, payload, Medication, 'manual_medication', session=session)


def edit_medication(patient_id: UUID, record_id: UUID, payload: MedicationEntry, *, session):
    return _record(patient_id, payload, Medication, 'manual_medication', record_id, session=session)


def add_allergy(patient_id: UUID, payload: AllergyEntry, *, session):
    return _record(patient_id, payload, Allergy, 'manual_allergy', session=session)


def edit_allergy(patient_id: UUID, record_id: UUID, payload: AllergyEntry, *, session):
    return _record(patient_id, payload, Allergy, 'manual_allergy', record_id, session=session)


def record_nkda(patient_id: UUID, payload: NoKnownDrugAllergies, *, session):

    def write(session, content):
        existing = session.scalar(select(Allergy).where(Allergy.patient_id == patient_id, Allergy.status == 'active', Allergy.category.in_(['drug', 'nkda'])))
        if existing:
            return _error('invalid_state', 'An active drug allergy or no-known-drug-allergy record already exists. Review that record first.')
        session.add(Allergy(id=uuid5(payload.submission_id, 'manual_nkda'), patient_id=patient_id, substance='No known drug allergies', category='nkda', reaction='None reported', severity='none', status='active', recorded_on=payload.recorded_on, verified_by='manual_patient_review_unverified_identity'))
    return _save(patient_id, payload, 'manual_nkda', write, session=session)


def add_problem(patient_id: UUID, payload: ProblemEntry, *, session):
    return _record(patient_id, payload, Condition, 'manual_problem', session=session)


def inactivate_allergy(patient_id: UUID, record_id: UUID, payload: Inactivate, *, session):

    def write(session, content):
        row = session.get(Allergy, record_id)
        if row is None or row.patient_id != patient_id:
            return _error('not_found', 'Allergy record not found for this patient.')
        before = row.status
        row.status = content['status']
        return {'record_id': str(record_id), 'before_status': before}
    return _save(patient_id, payload, f'allergy_status:{record_id}', write, session=session)


def save_visit_draft(patient_id: UUID, payload: VisitDraft, *, session):
    return _save(patient_id, payload, 'visit_draft', lambda *_: None, session=session)


def finalize_visit(patient_id, payload, *, session):
    def write(session, content):
        latest = session.scalar(select(AuditLog).where(AuditLog.patient_id == patient_id, AuditLog.action == 'visit_draft').order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1))
        if latest is None or latest.id != payload.draft_id:
            return _error('invalid_state', 'The saved draft changed. Reload and review the latest draft.')
        prior = session.scalars(select(AuditLog).where(AuditLog.patient_id == patient_id, AuditLog.action == 'finalize_visit')).all()
        if any(json.loads(row.detail)['input']['draft_id'] == str(payload.draft_id) for row in prior):
            return _error('invalid_state', 'This draft has already been finalized.')
        draft = json.loads(latest.detail)['input']
        if not draft['assessment'].strip() or not draft['plan'].strip():
            return _error('validation_error', 'Complete the assessment and plan before finalizing.')
        from datetime import date
        if date.fromisoformat(draft['visit_date']) > datetime.now(timezone.utc).date():
            return _error('validation_error', 'A future visit cannot be finalized.')
        now = datetime.now(timezone.utc)
        body = f"Visit date: {draft['visit_date']}\nFinalized by: {payload.finalized_by} (self-reported identity)\nFinalized at: {now.isoformat()}\n\nReason for visit / history\n{draft['reason']}\n\nAssessment\n{draft['assessment']}\n\nPlan\n{draft['plan']}"
        if len(body.encode()) > 7000:
            return _error('validation_error', 'The note exceeds the storage limit. Shorten the saved draft.')
        note_id = uuid5(payload.draft_id, 'finalized_visit_note')
        session.add(Note(id=note_id, patient_id=patient_id, body=body, created_at=now, embedding=None, source_suggestion_id=None))
        return {'note_id': str(note_id), 'visit_date': draft['visit_date']}
    return _save(patient_id, payload, 'finalize_visit', write, session=session)


def update_follow_up(patient_id: UUID, record_id: UUID, payload: FollowUp, *, session):

    def write(session, content):
        row = session.get(Reminder, record_id)
        if row is None or row.patient_id != patient_id:
            return _error('not_found', 'Follow-up record not found for this patient.')
        before = {'due_on': str(row.due_on), 'status': row.status}
        row.due_on, row.status = (payload.due_on, payload.status)
        return {'record_id': str(record_id), 'before': before}
    return _save(patient_id, payload, f'manual_follow_up:{record_id}', write, session=session)


def record_review(patient_id: UUID, payload: Review, *, session):

    def write(session, content):
        snapshot = _snapshot(session, patient_id, payload.kind)
        if payload.expected_version != _version(snapshot):
            return _error('invalid_state', 'The chart records changed. Reload and review the current records.')
        ids = {r['id'] for r in snapshot}
        if not ids:
            return _error('invalid_state', 'Add explicit chart records before recording a review. An empty list does not establish no known allergies or no medications.')
        if ids != {str(i) for i in payload.record_ids}:
            return _error('invalid_state', 'The chart list changed. Reload and review the current records.')
        if payload.kind == 'medications' and ids != {str(i) for i in payload.medication_use}:
            return _error('validation_error', 'Record patient-reported use for each medication.')
        return {'snapshot_version': _version(snapshot)}
    return _save(patient_id, payload, f'review_{payload.kind}', write, session=session)


def get_entry_state(patient_id: UUID, *, session):
    if session.get(Patient, patient_id) is None:
        return _error('not_found', 'Patient not found.')
    result = {'draft': None, 'medications': None, 'allergies': None, 'versions': {kind: _version(_snapshot(session, patient_id, kind)) for kind in ('medications', 'allergies')}}
    for key, action in [('draft', 'visit_draft'), ('medications', 'review_medications'), ('allergies', 'review_allergies')]:
        row = session.scalar(select(AuditLog).where(AuditLog.patient_id == patient_id, AuditLog.action == action).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1))
        if row:
            detail = json.loads(row.detail)
            result[key] = {**detail['input'], 'saved_at': row.created_at, 'stale': key != 'draft' and detail['snapshot_version'] != _version(_snapshot(session, patient_id, key))}
            if key == 'draft':
                finalized = session.scalars(select(AuditLog).where(AuditLog.patient_id == patient_id, AuditLog.action == 'finalize_visit')).all()
                receipt = next((r for r in finalized if json.loads(r.detail)['input']['draft_id'] == str(row.id)), None)
                result[key].update(draft_id=str(row.id), finalized_at=receipt.created_at if receipt else None, finalized_by=json.loads(receipt.detail)['input']['finalized_by'] if receipt else None)
    return result
