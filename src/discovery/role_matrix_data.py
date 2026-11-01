"""Role matrix data (computed by scripts/role_audit.py, read by /involved)."""
import json
from pathlib import Path

MATRIX_FILE = Path(__file__).resolve().parents[2] / "findings" / "role_matrix.json"


def get_matrix() -> dict:
    if not MATRIX_FILE.exists():
        return {}
    return json.loads(MATRIX_FILE.read_text())
