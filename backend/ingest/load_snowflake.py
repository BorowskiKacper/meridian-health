"""Load the three evidence corpora into Cortex Search.

The app does not import this module. Run it with the Snowflake settings from
backend/.env after fetch_corpus.py has written the jsonl files.
"""

import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app import config

ROOT = Path(__file__).resolve().parent
CORPUS = {
    config.USPSTF_SEARCH: ROOT / "corpus" / "uspstf.jsonl",
    config.PUBMED_SEARCH: ROOT / "corpus" / "pubmed.jsonl",
    config.PAYER_DOCS_SEARCH: ROOT / "corpus" / "payer_docs.jsonl",
}
_FIELDS = ("source_id", "title", "passage", "locator")


def _snowflake_host(account):
    host = account.strip()
    if host.startswith("https://"):
        host = host[len("https://") :]
    host = host.strip("/")
    if host.endswith(".snowflakecomputing.com"):
        return host
    return f"{host}.snowflakecomputing.com"


def _sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def _definition(rows):
    values = []
    for row in rows:
        values.append(
            "("
            + ", ".join(_sql_literal(row[field]) for field in _FIELDS)
            + ")"
        )
    select = ", ".join(
        f"column{index} AS {field}" for index, field in enumerate(_FIELDS, start=1)
    )
    return f"SELECT {select} FROM VALUES " + ", ".join(values)


def load_rows(service_name, rows, post):
    """Create or replace one Cortex Search service from citation rows."""
    database = quote(config.SNOWFLAKE_DATABASE.strip(), safe="")
    schema = quote(config.SNOWFLAKE_SCHEMA.strip(), safe="")
    service = quote(service_name, safe="")
    host = _snowflake_host(config.SNOWFLAKE_ACCOUNT)
    url = (
        f"https://{host}/api/v2/databases/{database}/schemas/{schema}"
        f"/cortex-search-services?createMode=orReplace&name={service}"
    )
    kept = [{field: row[field] for field in _FIELDS} for row in rows]
    post(
        url,
        headers={
            "Authorization": f"Bearer {config.SNOWFLAKE_PAT}",
            "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json={
            "name": service_name,
            "search_column": "passage",
            "target_lag": "1 day",
            "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE") or "COMPUTE_WH",
            "definition": _definition(kept),
        },
        timeout=60.0,
    )


def main():
    import httpx

    for service_name, path in CORPUS.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        load_rows(service_name, rows, httpx.post)


if __name__ == "__main__":
    main()
