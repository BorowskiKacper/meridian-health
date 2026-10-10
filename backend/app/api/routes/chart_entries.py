from fastapi import APIRouter
from uuid import UUID
from app.api.errors import finish
from app.schemas.chart_entries import Submission, Vitals, MedicationEntry, AllergyEntry, ProblemEntry, VisitDraft, Review, Inactivate, NoKnownDrugAllergies, FollowUp

router = APIRouter()


@router.post('/patients/{patient_id}/vitals')
def record_vitals(patient_id: UUID, payload: Vitals):
    import app.api.db as api_db
    import app.services.chart_entries as entries
    return finish(entries.record_vitals(patient_id, payload, session=api_db.get_session()))


@router.post('/patients/{patient_id}/medications')
def add_medication(patient_id: UUID, payload: MedicationEntry):
    import app.api.db as api_db
    import app.services.chart_entries as entries
    return finish(entries.add_medication(patient_id, payload, session=api_db.get_session()))


@router.put('/patients/{patient_id}/medications/{record_id}')
def edit_medication(patient_id: UUID, record_id: UUID, payload: MedicationEntry):
    import app.api.db as api_db
    import app.services.chart_entries as entries
    return finish(entries.edit_medication(patient_id, record_id, payload, session=api_db.get_session()))


@router.post('/patients/{patient_id}/allergies')
def add_allergy(patient_id: UUID, payload: AllergyEntry):
    import app.api.db as api_db
    import app.services.chart_entries as entries
    return finish(entries.add_allergy(patient_id, payload, session=api_db.get_session()))


@router.put('/patients/{patient_id}/allergies/{record_id}')
def edit_allergy(patient_id: UUID, record_id: UUID, payload: AllergyEntry):
    import app.api.db as api_db
    import app.services.chart_entries as entries
    return finish(entries.edit_allergy(patient_id, record_id, payload, session=api_db.get_session()))


@router.post('/patients/{patient_id}/no-known-drug-allergies')
def record_nkda(patient_id: UUID, payload: NoKnownDrugAllergies):
    import app.api.db as api_db
    import app.services.chart_entries as entries
    return finish(entries.record_nkda(patient_id, payload, session=api_db.get_session()))


@router.post('/patients/{patient_id}/problems')
def add_problem(patient_id: UUID, payload: ProblemEntry):
    import app.api.db as api_db
    import app.services.chart_entries as entries
    return finish(entries.add_problem(patient_id, payload, session=api_db.get_session()))


@router.put('/patients/{patient_id}/allergies/{record_id}/status')
def inactivate_allergy(patient_id: UUID, record_id: UUID, payload: Inactivate):
    import app.api.db as api_db
    import app.services.chart_entries as entries
    return finish(entries.inactivate_allergy(patient_id, record_id, payload, session=api_db.get_session()))


@router.post('/patients/{patient_id}/visit-draft')
def save_visit_draft(patient_id: UUID, payload: VisitDraft):
    import app.api.db as api_db
    import app.services.chart_entries as entries
    return finish(entries.save_visit_draft(patient_id, payload, session=api_db.get_session()))


@router.put('/patients/{patient_id}/follow-up/{record_id}')
def update_follow_up(patient_id: UUID, record_id: UUID, payload: FollowUp):
    import app.api.db as api_db
    import app.services.chart_entries as entries
    return finish(entries.update_follow_up(patient_id, record_id, payload, session=api_db.get_session()))


@router.post('/patients/{patient_id}/chart-review')
def record_review(patient_id: UUID, payload: Review):
    import app.api.db as api_db
    import app.services.chart_entries as entries
    return finish(entries.record_review(patient_id, payload, session=api_db.get_session()))


@router.get('/patients/{patient_id}/entry-state')
def get_entry_state(patient_id: UUID):
    import app.api.db as api_db
    import app.services.chart_entries as entries
    return finish(entries.get_entry_state(patient_id, session=api_db.get_session()))


