from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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

app = FastAPI()
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
