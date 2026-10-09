"""Make `import app` and a file load of backend/seed/seed.py work without an install."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
backend_path = str(BACKEND_DIR)
if backend_path in sys.path:
    sys.path.remove(backend_path)
sys.path.insert(0, backend_path)
