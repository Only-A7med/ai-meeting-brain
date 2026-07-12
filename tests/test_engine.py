from app.engine import MemoryEngine


# ── query parsing ────────────────────────────────────────────────

def test_detect_intent(seeded_engine):
    e = seeded_engine
    assert e._detect_intent("What did Ahmed promise?") == "commitment"
    assert e._detect_intent("what decisions were made?") == "decision"
    assert e._detect_intent("anything overdue?") == "deadline"
    assert e._detect_intent("which meetings mention azure?") == "mention"
    assert e._detect_intent("tell me about the pilot rollout") == "search"


def test_detect_person(seeded_engine):
    assert seeded_engine._detect_person("what did AHMED promise?") == "Ahmed"
    assert seeded_engine._detect_person("what about the roadmap?") is None
    assert seeded_engine._detect_person("the saratoga account") is None


def test_timerange_months_ago(seeded_engine):
    assert seeded_engine._detect_timerange("what happened six months ago?") == \
        ("2026-01-01", "2026-01-31", "around January 2026")
    assert seeded_engine._detect_timerange("2 months ago") == \
        ("2026-05-01", "2026-05-31", "around May 2026")
    assert seeded_engine._detect_timerange("twelve months ago") == \
        ("2025-07-01", "2025-07-31", "around July 2025")


def test_timerange_relative(seeded_engine):
    assert seeded_engine._detect_timerange("last month") == ("2026-06-01", "2026-06-30", "in June 2026")
    assert seeded_engine._detect_timerange("last week") == ("2026-07-05", "2026-07-12", "in the last week")
    assert seeded_engine._detect_timerange("this year") == ("2026-01-01", "2026-07-12", "in 2026")


def test_timerange_named_month(seeded_engine):
    assert seeded_engine._detect_timerange("back in march") == ("2026-03-01", "2026-03-31", "in March 2026")
    assert seeded_engine._detect_timerange("during december") == ("2025-12-01", "2025-12-31", "in December 2025")
    assert seeded_engine._detect_timerange("no time expression") is None


# ── delivery settlement ──────────────────────────────────────────

COMMIT_LINE = {"speaker": "Ali", "text": "I'll draft the onboarding guide by March 20."}


def test_delivery_settles_commitment_and_deadline(engine):
    engine.ingest("Sprint", "2026-03-02", "P", ["Ali"], [COMMIT_LINE])
    engine.ingest("Sync", "2026-03-16", "P", ["Ali"],
                  [{"speaker": "Ali", "text": "I've finished the onboarding guide draft."}])
    commitment, = engine.commitments
    assert commitment.status == "delivered"
    assert commitment.delivered_on == "2026-03-16"
    deadline, = engine.deadlines
    assert deadline.status == "done"


def test_delivery_by_other_person_does_not_settle(engine):
    engine.ingest("Sprint", "2026-03-02", "P", ["Ali"], [COMMIT_LINE])
    engine.ingest("Sync", "2026-03-16", "P", ["Rana"],
                  [{"speaker": "Rana", "text": "I've finished the onboarding guide draft."}])
    assert engine.commitments[0].status == "open"


def test_unrelated_delivery_does_not_settle(engine):
    engine.ingest("Sprint", "2026-03-02", "P", ["Ali"], [COMMIT_LINE])
    engine.ingest("Sync", "2026-03-16", "P", ["Ali"],
                  [{"speaker": "Ali", "text": "I've finished the budget spreadsheet."}])
    assert engine.commitments[0].status == "open"


# ── flagship queries (asserted exactly) ──────────────────────────

def test_flagship_ahmed_six_months_ago(seeded_engine):
    r = seeded_engine.ask("What did Ahmed promise six months ago?")
    assert r["intent"] == "commitments"
    assert r["answer"] == "Ahmed made 2 commitments around January 2026 — 2 delivered, 0 still open."
    assert [c["date"] for c in r["items"]] == ["2026-01-06", "2026-01-13"]
    assert all(c["status"] == "delivered" and c["person"] == "Ahmed" for c in r["items"])


def test_flagship_atlas_decisions(seeded_engine):
    r = seeded_engine.ask("What decisions were made about Project Atlas?")
    assert r["intent"] == "decisions"
    assert r["answer"] == '6 decisions on record about "atlas".'
    assert len(r["items"]) == 6


def test_flagship_azure_mentions(seeded_engine):
    r = seeded_engine.ask("Which meetings mention Azure?")
    assert r["intent"] == "mentions"
    assert r["answer"] == '"azure" comes up in 8 meetings.'
    assert len(r["items"]) == 8


def test_flagship_overdue_deadlines(seeded_engine):
    r = seeded_engine.ask("What deadlines are overdue?")
    assert r["intent"] == "deadlines"
    assert r["answer"] == "4 deadlines are overdue as of today."
    assert len(r["items"]) == 4
    assert all(d["overdue"] for d in r["items"])


# ── views & persistence ──────────────────────────────────────────

def test_stats(seeded_engine):
    s = seeded_engine.stats()
    assert s["meetings"] == 16
    assert s["deadlines_overdue"] == 4
    assert s["first_meeting"] == "2026-01-06"
    assert s["last_meeting"] == "2026-07-06"
    assert "Ahmed" in s["people"]


def test_search_fallback_intent(seeded_engine):
    r = seeded_engine.ask("tell me about identity resolution match rate")
    assert r["intent"] == "search"
    assert r["citations"]


def test_persistence_roundtrip(engine):
    engine.ingest("Sprint", "2026-03-02", "P", ["Ali"], [COMMIT_LINE])
    engine.save()
    reloaded = MemoryEngine(engine.store_path)
    assert len(reloaded.meetings) == 1
    assert len(reloaded.commitments) == 1
    assert reloaded.index.search("onboarding")
