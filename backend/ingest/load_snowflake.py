"""Load the ingest corpora into Snowflake and create the Cortex Search services.

Snowflake is called over its SQL REST API with httpx. This script does not use
a Snowflake connector. It uploads only the de-identified passages in
backend/ingest/corpus (USPSTF, PubMed, and payer documents).

    python ingest/load_snowflake.py

Requires SNOWFLAKE_ACCOUNT, SNOWFLAKE_PAT, SNOWFLAKE_DATABASE, and
SNOWFLAKE_SCHEMA. SNOWFLAKE_WAREHOUSE defaults to COMPUTE_WH.
"""

import os
import sys
import time
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app import config
from app.evidence.corpus import load_rows
from app.evidence.cortex import _snowflake_host, snowflake_configured

SERVICES = (
    config.USPSTF_SEARCH,
    config.PUBMED_SEARCH,
    config.PAYER_DOCS_SEARCH,
)
TABLES = {
    config.USPSTF_SEARCH: "uspstf_passages",
    config.PUBMED_SEARCH: "pubmed_passages",
    config.PAYER_DOCS_SEARCH: "payer_docs_passages",
}
BATCH = 20
_PENDING = {"333334", "333335"}


def quote_ident(name):
    return '"' + str(name).replace('"', '""') + '"'


def sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def create_table_sql(service_name):
    table = TABLES[service_name]
    return (
        f"CREATE OR REPLACE TABLE {table} ("
        "source_id VARCHAR, title VARCHAR, passage VARCHAR, locator VARCHAR)"
    )


def insert_sql(service_name, rows):
    table = TABLES[service_name]
    values = []
    for row in rows:
        values.append(
            "("
            + ", ".join(
                sql_literal(row[field])
                for field in ("source_id", "title", "passage", "locator")
            )
            + ")"
        )
    return (
        f"INSERT INTO {table} (source_id, title, passage, locator) VALUES "
        + ", ".join(values)
    )


def create_service_sql(service_name, warehouse):
    table = TABLES[service_name]
    return (
        f"CREATE OR REPLACE CORTEX SEARCH SERVICE {service_name} "
        "ON passage "
        "ATTRIBUTES source_id, title, locator "
        f"WAREHOUSE = {quote_ident(warehouse)} "
        "TARGET_LAG = '1 hour' "
        f"AS (SELECT source_id, title, passage, locator FROM {table})"
    )


def statements_for_service(service_name, rows, warehouse):
    statements = [create_table_sql(service_name)]
    for start in range(0, len(rows), BATCH):
        batch = rows[start : start + BATCH]
        if batch:
            statements.append(insert_sql(service_name, batch))
    statements.append(create_service_sql(service_name, warehouse))
    return statements


def setup_statements(database, schema):
    database_sql = quote_ident(database)
    schema_sql = quote_ident(schema)
    return [
        f"CREATE DATABASE IF NOT EXISTS {database_sql}",
        f"CREATE SCHEMA IF NOT EXISTS {database_sql}.{schema_sql}",
    ]


def _headers(pat):
    return {
        "Authorization": f"Bearer {pat}",
        "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "hackknight-emr/snowflake",
    }


def _payload(response):
    if response.status_code >= 400:
        raise RuntimeError(
            f"Snowflake SQL API returned {response.status_code}: {response.text[:500]}"
        )
    return response.json()


def execute_statement(
    client, account, pat, statement, *, database=None, schema=None, warehouse=None
):
    host = _snowflake_host(account)
    body = {"statement": statement, "timeout": 60}
    if database:
        body["database"] = database
    if schema:
        body["schema"] = schema
    if warehouse:
        body["warehouse"] = warehouse
    response = client.post(
        f"https://{host}/api/v2/statements",
        headers=_headers(pat),
        json=body,
        timeout=90.0,
    )
    payload = _payload(response)
    for _ in range(30):
        pending = response.status_code == 202 or str(payload.get("code")) in _PENDING
        if not pending:
            break
        handle = payload.get("statementHandle")
        if not handle:
            raise RuntimeError("Snowflake statement is still running and returned no handle")
        time.sleep(1)
        response = client.get(
            f"https://{host}/api/v2/statements/{handle}",
            headers=_headers(pat),
            timeout=90.0,
        )
        payload = _payload(response)
    else:
        raise RuntimeError("Snowflake statement did not finish")
    if payload.get("sqlState") not in (None, "00000"):
        raise RuntimeError(payload.get("message") or "Snowflake statement failed")
    return payload


def load_corpora(client=None):
    if not snowflake_configured():
        raise RuntimeError(
            "Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_PAT, SNOWFLAKE_DATABASE, and "
            "SNOWFLAKE_SCHEMA before loading corpora."
        )
    warehouse = os.environ.get("SNOWFLAKE_WAREHOUSE", "").strip() or "COMPUTE_WH"
    own_client = client is None
    if own_client:
        client = httpx.Client()
    try:
        for statement in setup_statements(config.SNOWFLAKE_DATABASE, config.SNOWFLAKE_SCHEMA):
            execute_statement(
                client,
                config.SNOWFLAKE_ACCOUNT,
                config.SNOWFLAKE_PAT,
                statement,
            )
        for service_name in SERVICES:
            rows = load_rows(service_name)
            for statement in statements_for_service(service_name, rows, warehouse):
                execute_statement(
                    client,
                    config.SNOWFLAKE_ACCOUNT,
                    config.SNOWFLAKE_PAT,
                    statement,
                    database=config.SNOWFLAKE_DATABASE,
                    schema=config.SNOWFLAKE_SCHEMA,
                    warehouse=warehouse,
                )
    finally:
        if own_client:
            client.close()


def main():
    load_corpora()


if __name__ == "__main__":
    main()
