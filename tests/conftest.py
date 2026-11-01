"""Make `pytest tests` work from a clean project root without PYTHONPATH:
adds <repo>/src to sys.path for the test session.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
