from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import app.api.db as api_db
import app.runtime as runtime
from app.api.errors import validation_message
from app.api.routes import (
    appointments,
    body,
    chart_entries,
    documents,
    eligibility,
    reminders,
    requests,
    secretary,
    suggestions,
    webhooks,
)

app = FastAPI()
# The Expo client sends X-Role from a browser origin. Native clients ignore CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(body.router)
app.include_router(chart_entries.router)
app.include_router(requests.router)
app.include_router(suggestions.router)
app.include_router(documents.router)
app.include_router(reminders.router)
app.include_router(eligibility.router)
app.include_router(appointments.router)
app.include_router(secretary.router)
app.include_router(webhooks.router)


@app.middleware("http")
async def request_session(request: Request, call_next):
    if api_db.tests_replaced_session():
        return await call_next(request)
    token = runtime.open_request_session()
    try:
        response = await call_next(request)
    except Exception:
        runtime.close_request_session(token, commit=False)
        raise
    runtime.close_request_session(token, commit=response.status_code < 400)
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
