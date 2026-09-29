import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import haiku


@pytest.fixture(autouse=True)
def instant_retries(monkeypatch):
    """Retry backoff must never make the suite wait in real time."""
    monkeypatch.setattr(haiku, 'time', SimpleNamespace(sleep=lambda seconds: None))
