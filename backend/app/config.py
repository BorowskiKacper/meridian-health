"""Settings loaded from the environment. Unset names are empty strings."""

import os
from pathlib import Path

from dotenv import load_dotenv

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
if _ENV_FILE.is_file():
    load_dotenv(_ENV_FILE)

GEMINI_MODEL = "gemini-3.6-flash"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768
USPSTF_SEARCH = "USPSTF_SEARCH"
PUBMED_SEARCH = "PUBMED_SEARCH"
PAYER_DOCS_SEARCH = "PAYER_DOCS_SEARCH"
MEDICAL_DOMAINS = (
    "uspreventiveservicestaskforce.org",
    "cdc.gov",
    "nih.gov",
    "cancer.gov",
    "fda.gov",
    "cancer.org",
    "heart.org",
    "ahajournals.org",
    "acc.org",
    "diabetesjournals.org",
    "gastro.org",
    "gi.org",
    "asge.org",
    "acog.org",
    "auanet.org",
    "aafp.org",
    "acponline.org",
    "cochranelibrary.com",
    "who.int",
    "nice.org.uk",
)

_ENV_NAMES = (
    "DATABASE_URL",
    "GEMINI_API_KEY",
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_PAT",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_FROM_NUMBER",
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_VOICE_ID",
    "S3_BUCKET",
    "S3_REGION",
)


def _setting(name):
    value = os.environ.get(name)
    if isinstance(value, str):
        return value
    return ""


for _name in _ENV_NAMES:
    globals()[_name] = _setting(_name)
