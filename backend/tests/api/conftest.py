import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_API_DIR = Path(__file__).resolve().parent
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)
