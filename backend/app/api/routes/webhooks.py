from fastapi import APIRouter, Form
from starlette.responses import Response

router = APIRouter()


@router.post("/webhooks/twilio")
def twilio_webhook(
    MessageSid: str = Form(...),
    MessageStatus: str = Form(...),
    From: str = Form(...),
    Body: str = Form(...),
):
    import app.api.db as api_db
    import app.services.sms as sms

    session = api_db.get_session()
    sms.handle_sms_webhook(
        {
            "MessageSid": MessageSid,
            "MessageStatus": MessageStatus,
            "From": From,
            "Body": Body,
        },
        session=session,
    )
    return Response(content=b"", status_code=200)
