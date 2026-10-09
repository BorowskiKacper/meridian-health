from fastapi import FastAPI

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
