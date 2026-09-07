from app.seed_data import REFERENCE_DATE


def ask(client, query):
    r = client.post("/api/ask", json={"query": query})
    assert r.status_code == 200
    return r.json()


def test_stats(client):
    s = client.get("/api/stats").json()
    assert s["meetings"] == 16
    assert s["deadlines_overdue"] == 4
    assert "Ahmed" in s["people"]


def test_meetings_sorted_desc(client):
    items = client.get("/api/meetings").json()
    assert len(items) == 16
    dates = [m["date"] for m in items]
    assert dates == sorted(dates, reverse=True)


def test_meeting_detail_and_404(client):
    first = client.get("/api/meetings").json()[-1]
    detail = client.get(f"/api/meetings/{first['id']}").json()
    assert detail["segments"]
    assert {"commitments", "decisions", "deadlines"} <= detail.keys()
    assert client.get("/api/meetings/nope").status_code == 404


def test_flagship_ahmed_six_months_ago(client):
    r = ask(client, "What did Ahmed promise six months ago?")
    assert r["intent"] == "commitments"
    assert r["answer"] == "Ahmed made 2 commitments around January 2026 — 2 delivered, 0 still open."
    assert [c["date"] for c in r["items"]] == ["2026-01-06", "2026-01-13"]
    assert all(c["status"] == "delivered" for c in r["items"])


def test_flagship_atlas_decisions(client):
    r = ask(client, "What decisions were made about Project Atlas?")
    assert r["intent"] == "decisions"
    assert r["answer"] == '6 decisions on record about "atlas".'
    assert len(r["items"]) == 6


def test_flagship_azure_mentions(client):
    r = ask(client, "Which meetings mention Azure?")
    assert r["intent"] == "mentions"
    assert r["answer"] == '"azure" comes up in 8 meetings.'
    assert len(r["items"]) == 8


def test_flagship_overdue_deadlines(client):
    r = ask(client, "What deadlines are overdue?")
    assert r["intent"] == "deadlines"
    assert r["answer"] == "4 deadlines are overdue as of today."
    assert len(r["items"]) == 4
    assert all(d["overdue"] for d in r["items"])


def test_ask_rejects_empty_query(client):
    assert client.post("/api/ask", json={"query": "   "}).status_code == 422


def test_commitments_filters(client):
    items = client.get("/api/commitments", params={"person": "ahmed"}).json()
    assert items and all(c["person"] == "Ahmed" for c in items)
    open_items = client.get("/api/commitments", params={"status": "open"}).json()
    assert all(c["status"] == "open" for c in open_items)


def test_decisions_filter(client):
    items = client.get("/api/decisions", params={"project": "phoenix mobile"}).json()
    assert items and all(d["project"] == "Phoenix Mobile" for d in items)


def test_deadlines_overdue_filter(client):
    items = client.get("/api/deadlines", params={"overdue": "true"}).json()
    assert len(items) == 4
    assert all(d["overdue"] for d in items)


def test_home_serves_ui(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Meeting Brain" in r.text


# Mutates shared app state — keep after the read-only assertions above.
def test_ingest_validation_and_extraction(client):
    bad_date = client.post("/api/meetings", json={
        "title": "X", "date": "07/10/2026", "project": "P", "transcript": "A: hi"})
    assert bad_date.status_code == 422
    no_lines = client.post("/api/meetings", json={
        "title": "X", "date": "2026-07-10", "project": "P", "transcript": "nothing usable here"})
    assert no_lines.status_code == 422

    r = client.post("/api/meetings", json={
        "title": "Vendor sync", "date": "2026-07-10", "project": "Procurement",
        "transcript": "Zara: I'll circulate the vendor shortlist by December 20.\n"
                      "Bilal: We decided to renew the support contract.",
    })
    assert r.status_code == 200
    detail = client.get(f"/api/meetings/{r.json()['id']}").json()
    assert detail["attendees"] == ["Zara", "Bilal"]
    assert len(detail["commitments"]) == 1
    assert detail["commitments"][0]["due"] == "2026-12-20"
    assert len(detail["decisions"]) == 1
    assert len(detail["deadlines"]) == 1
    assert not detail["deadlines"][0]["overdue"]


# Mutates shared app state — keep after the read-only assertions above.
def test_ingest_handles_timestamps_and_urls(client):
    r = client.post("/api/meetings", json={
        "title": "Exported sync", "date": "2026-07-11", "project": "Procurement",
        "transcript": "[00:00:04] Zara: I'll circulate the vendor shortlist by December 20.\n"
                      "See https://example.com/deck for the slides.\n"
                      "(0:31) Bilal: We decided to renew the support contract.\n",
    })
    assert r.status_code == 200
    detail = client.get(f"/api/meetings/{r.json()['id']}").json()
    assert detail["attendees"] == ["Zara", "Bilal"]
    assert detail["commitments"][0]["person"] == "Zara"
    assert detail["commitments"][0]["due"] == "2026-12-20"
    assert detail["decisions"][0]["speaker"] == "Bilal"


def test_ingest_rejects_transcript_of_only_urls(client):
    r = client.post("/api/meetings", json={
        "title": "Links", "date": "2026-07-11", "project": "P",
        "transcript": "See https://example.com for the deck.\nhttps://example.com\n",
    })
    assert r.status_code == 422


def test_stats_reports_the_pinned_demo_clock(client):
    s = client.get("/api/stats").json()
    assert s["today"] == REFERENCE_DATE
    assert s["pinned_clock"] is True
