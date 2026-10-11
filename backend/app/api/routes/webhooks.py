from fastapi import APIRouter
from starlette.responses import PlainTextResponse

router = APIRouter()


@router.get("/email/unsubscribe")
def email_unsubscribe(token: str = ""):
    import app.api.db as api_db
    import app.services.email as email

    with api_db.get_session() as session:
        message = email.unsubscribe(token, session=session)
        if message is None:
            return PlainTextResponse("This unsubscribe link is not valid.", status_code=400)
        return PlainTextResponse(message)
