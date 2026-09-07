import os
import tempfile
from datetime import date
from pathlib import Path

import pytest

from app.seed_data import MEETINGS, REFERENCE_DATE

TODAY = date.fromisoformat(REFERENCE_DATE)

# Point the app at a throwaway store, and pin its clock to the date the seeded
# archive was written against, before app.main is ever imported.
os.environ.setdefault("MEETING_BRAIN_STORE", str(Path(tempfile.mkdtemp()) / "store.json"))
os.environ.setdefault("MEETING_BRAIN_TODAY", REFERENCE_DATE)

from app.engine import MemoryEngine  # noqa: E402


@pytest.fixture(scope="session")
def seeded_engine(tmp_path_factory):
    eng = MemoryEngine(tmp_path_factory.mktemp("mem") / "store.json", today=TODAY)
    for m in MEETINGS:
        eng.ingest(m["title"], m["date"], m["project"], m["attendees"], m["segments"])
    return eng


@pytest.fixture
def engine(tmp_path):
    return MemoryEngine(tmp_path / "store.json", today=TODAY)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
