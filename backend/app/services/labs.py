from datetime import datetime, timezone
from uuid import uuid4

import boto3

from app.config import S3_BUCKET, S3_REGION
from app.db.repositories import insert_document, insert_suggestion
from app.schemas import Suggestion

_FLAGGED = frozenset({"low_confidence", "out_of_range"})


def save_object(storage_key, content):
    if not S3_BUCKET:
        raise RuntimeError("S3_BUCKET is not set.")
    client_kwargs = {}
    if S3_REGION:
        client_kwargs["region_name"] = S3_REGION
    client = boto3.client("s3", **client_kwargs)
    client.put_object(Bucket=S3_BUCKET, Key=storage_key, Body=content)


def extract_analytes(content, media_type) -> list:
    return []


def _validation_flags(flag):
    if flag in _FLAGGED:
        return [flag]
    return []


def _suggestion_payload(patient_id, analyte):
    return {
        "id": str(uuid4()),
        "patient_id": patient_id,
        "request_id": None,
        "kind": "observation",
        "status": "pending",
        "target_table": "observations",
        "target_id": None,
        "before": {},
        "after": {
            "name": analyte["name"],
            "value": analyte["value"],
            "unit": analyte["unit"],
            "observed_at": analyte["observed_at"],
        },
        "reason": "Extracted from a lab report photo",
        "confidence": analyte["confidence"],
        "citations": [],
        "validation_flags": _validation_flags(analyte.get("flag")),
        "source": "lab_report",
    }


def extract_lab_report(patient_id, content, media_type, *, session):
    document_id = str(uuid4())
    storage_key = f"{patient_id}/{document_id}.bin"
    save_object(storage_key, content)

    document = insert_document(
        session,
        {
            "id": document_id,
            "patient_id": patient_id,
            "storage_key": storage_key,
            "media_type": media_type,
            "uploaded_at": datetime.now(timezone.utc),
        },
    )

    analytes = extract_analytes(content, media_type)
    suggestions = []
    for analyte in analytes:
        suggestion = Suggestion.model_validate(_suggestion_payload(patient_id, analyte))
        stored = insert_suggestion(
            session,
            suggestion.model_dump(exclude={"unconfirmed"}),
        )
        suggestions.append(stored)

    return {
        "document_id": document["id"],
        "analytes": analytes,
        "suggestions": suggestions,
    }
