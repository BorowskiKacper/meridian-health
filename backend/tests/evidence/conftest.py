import sys
from pathlib import Path

EVIDENCE_TESTS = str(Path(__file__).resolve().parent)
BACKEND_DIR = str(Path(__file__).resolve().parents[2])
if EVIDENCE_TESTS not in sys.path:
    sys.path.insert(0, EVIDENCE_TESTS)
if sys.path[:1] != [BACKEND_DIR]:
    sys.path.insert(0, BACKEND_DIR)
