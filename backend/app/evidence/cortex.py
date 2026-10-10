"""Snowflake Cortex Search over the loaded guideline and payer corpora."""

from urllib.parse import quote

import httpx

from app import config

_COLUMNS = ["source_id", "title", "passage", "locator"]


def _snowflake_host(account):
    host = account.strip()
    if host.startswith("https://"):
        host = host[len("https://") :]
    host = host.strip("/")
    if host.endswith(".snowflakecomputing.com"):
        return host
    return f"{host}.snowflakecomputing.com"


def cortex_search(service_name, text):
    """Query one Cortex Search service and return citation rows.

    Each row has source_id, title, passage, and locator.
    """
    database = quote(config.SNOWFLAKE_DATABASE.strip(), safe="")
    schema = quote(config.SNOWFLAKE_SCHEMA.strip(), safe="")
    service = quote(service_name, safe="")
    host = _snowflake_host(config.SNOWFLAKE_ACCOUNT)
    url = (
        f"https://{host}/api/v2/databases/{database}/schemas/{schema}"
        f"/cortex-search-services/{service}:query"
    )
    response = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {config.SNOWFLAKE_PAT}",
            "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json={"query": text, "columns": _COLUMNS, "limit": 10},
        timeout=30.0,
    )
    response.raise_for_status()
    rows = response.json().get("results") or []
    return [
        {
            "source_id": row["source_id"],
            "title": row["title"],
            "passage": row["passage"],
            "locator": row["locator"],
        }
        for row in rows
    ]
