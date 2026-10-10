from datetime import timezone

from fastapi.responses import JSONResponse

_STATUS = {
    "validation_error": 400,
    "wrong_role": 403,
    "not_found": 404,
    "invalid_state": 409,
}


def error_response(code, message):
    return JSONResponse(
        status_code=_STATUS[code],
        content={"error": {"code": code, "message": message}},
    )


def finish(result):
    if not isinstance(result, dict) or set(result) != {"error"}:
        return result
    error = result.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    status = _STATUS.get(code, 400)
    return JSONResponse(status_code=status, content=result)


def reject_unless_secretary(role):
    if role is None:
        role = "doctor"
    if role != "secretary":
        return error_response(
            "wrong_role",
            "This route requires the secretary role.",
        )
    return None


def as_aware(value):
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def validation_message(exc):
    parts = []
    for item in exc.errors():
        location = [
            str(part)
            for part in item.get("loc", ())
            if part not in ("body", "query", "header", "path")
        ]
        detail = str(item.get("msg", "")).strip()
        if location and detail:
            parts.append(f"{'.'.join(location)} {detail}")
        elif detail:
            parts.append(detail)
    message = "; ".join(parts).strip()
    return message or "Request validation failed."
