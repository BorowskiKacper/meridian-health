from fastapi import APIRouter, Query

from app.api.errors import finish

router = APIRouter()


@router.get("/patients/search")
def search_patients(q: str = Query(default="", max_length=200), limit: int = Query(default=20, ge=1, le=20)):
    import app.api.db as api_db
    import app.services.patient_search as patient_search

    return finish(patient_search.search_patients(q, limit, session=api_db.get_session()))


@router.get("/patients")
def list_patients():
    import app.api.db as api_db
    import app.services.chart as chart

    session = api_db.get_session()
    result = chart.list_chart_patients(session=session)
    return finish(result)


@router.get("/patients/{patient_id}/chart")
def get_chart(patient_id: str):
    import app.api.db as api_db
    import app.services.chart as chart

    session = api_db.get_session()
    result = chart.get_chart(patient_id, session=session)
    return finish(result)


@router.get("/patients/{patient_id}/body-state")
def get_body_state(patient_id: str, specialty: str):
    import app.api.db as api_db
    import app.services.chart as chart

    session = api_db.get_session()
    result = chart.get_body_state(patient_id, specialty, session=session)
    return finish(result)


@router.get("/patients/{patient_id}/regions/{region_key}")
def get_region(patient_id: str, region_key: str):
    import app.api.db as api_db
    import app.services.chart as chart

    session = api_db.get_session()
    result = chart.get_region(patient_id, region_key, session=session)
    return finish(result)
