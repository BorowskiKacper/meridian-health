import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[2])
if sys.path[:1] != [BACKEND_DIR]:
    sys.path.insert(0, BACKEND_DIR)
