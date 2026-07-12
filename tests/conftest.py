import os
import tempfile
from datetime import date
from pathlib import Path

import pytest

# Point the app at a throwaway store before app.main is ever imported.
os.environ.setdefault("MEETING_BRAIN_STORE", str(Path(tempfile.mkdtemp()) / "store.json"))

import app.engine as engine_module
from app.engine import MemoryEngine
from app.seed_data import MEETINGS

TODAY = date(2026, 7, 12)


class FrozenDate(date):
    @classmethod
    def today(cls):
        return cls(TODAY.year, TODAY.month, TODAY.day)


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(engine_module, "date", FrozenDate)


@pytest.fixture(scope="session")
def seeded_engine(tmp_path_factory):
    eng = MemoryEngine(tmp_path_factory.mktemp("mem") / "store.json")
    for m in MEETINGS:
        eng.ingest(m["title"], m["date"], m["project"], m["attendees"], m["segments"])
    return eng


@pytest.fixture
def engine(tmp_path):
    return MemoryEngine(tmp_path / "store.json")


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
