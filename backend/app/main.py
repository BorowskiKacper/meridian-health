import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.errors import validation_message
from app.api.routes import (
    appointments,
    body,
    documents,
    eligibility,
    reminders,
    requests,
    secretary,
    suggestions,
    webhooks,
)


@asynccontextmanager
async def _lifespan(_app):
    if os.environ.get("EMR_BIND_DB") == "1":
        from app.api.db import prepare_database

        prepare_database()
    yield


app = FastAPI(lifespan=_lifespan)


@app.middleware("http")
async def bind_database_session(request: Request, call_next):
    if os.environ.get("EMR_BIND_DB") != "1":
        return await call_next(request)
    from app.api import db as api_db

    session = Session(api_db.get_engine())
    token = api_db.bind_session(session)
    try:
        response = await call_next(request)
        session.commit()
        return response
    except Exception:
        session.rollback()
        raise
    finally:
        api_db.reset_session(token)
        session.close()
app.include_router(body.router)
app.include_router(requests.router)
app.include_router(suggestions.router)
app.include_router(documents.router)
app.include_router(reminders.router)
app.include_router(eligibility.router)
app.include_router(appointments.router)
app.include_router(secretary.router)
app.include_router(webhooks.router)


@app.exception_handler(RequestValidationError)
async def request_validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "validation_error",
                "message": validation_message(exc),
            }
        },
    )
