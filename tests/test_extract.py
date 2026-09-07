from app.extract import extract_from_meeting, parse_due, parse_transcript
from app.models import Meeting, Segment


def extract(date_str, *lines):
    meeting = Meeting(
        id="m1", title="Test", date=date_str, project="Test",
        attendees=sorted({sp for sp, _ in lines}),
        segments=[Segment(speaker=sp, text=tx) for sp, tx in lines],
    )
    return extract_from_meeting(meeting)


def test_commitment_basic():
    comms, _, _, _ = extract("2026-07-01", ("Ahmed", "I'll deliver the quarterly report by July 20."))
    assert comms == [{"person": "Ahmed", "text": "Deliver the quarterly report by July 20", "due": "2026-07-20"}]


def test_commitment_variants():
    comms, _, _, _ = extract(
        "2026-07-01",
        ("A", "I will review the security document this week."),
        ("B", "I'm going to refactor the ingest parser."),
        ("C", "I can take care of the vendor follow-up."),
        ("D", "Leave that with me, the rollout checklist is mine."),
    )
    assert [c["person"] for c in comms] == ["A", "B", "C", "D"]
    assert all(c["due"] is None for c in comms)


def test_short_commitment_filtered():
    comms, _, _, _ = extract("2026-07-01", ("A", "I'll do it."))
    assert comms == []


def test_delivery_beats_commitment():
    comms, _, _, deliveries = extract("2026-07-01", ("A", "I've finished the migration runbook draft."))
    assert comms == []
    assert deliveries == [{"person": "A", "text": "The migration runbook draft"}]


def test_delivery_variants():
    _, _, _, deliveries = extract(
        "2026-07-01",
        ("A", "I've just shipped the billing exporter."),
        ("B", "I delivered the cost estimate to finance."),
        ("C", "I've closed out the legal sign-off."),
    )
    assert len(deliveries) == 3


def test_delivery_without_perfect_tense():
    _, _, _, deliveries = extract("2026-07-01", ("A", "I closed out the legal sign-off."))
    assert deliveries == [{"person": "A", "text": "The legal sign-off"}]


def test_decision_variants():
    _, decs, _, _ = extract(
        "2026-07-01",
        ("A", "We decided to adopt trunk-based development."),
        ("B", "We agreed on a quarterly release cadence."),
        ("C", "We're going with Postgres for the ledger."),
        ("D", "Let's go with the phased rollout."),
        ("E", "Decision: sunset the legacy exporter."),
    )
    assert [d["speaker"] for d in decs] == ["A", "B", "C", "D", "E"]
    assert decs[0]["text"] == "Adopt trunk-based development"
    assert decs[4]["text"] == "Sunset the legacy exporter"


def test_decision_takes_precedence_over_commitment():
    comms, decs, _, _ = extract("2026-07-01", ("A", "We decided that I'll own the incident review process."))
    assert len(decs) == 1
    assert comms == []


def test_parse_due_forms():
    assert parse_due("done by June 26", "2026-06-02") == "2026-06-26"
    assert parse_due("it is due on March 3", "2026-02-20") == "2026-03-03"
    assert parse_due("the deadline is March 3", "2026-02-20") == "2026-03-03"
    assert parse_due("done by june 26", "2026-06-02") == "2026-06-26"
    assert parse_due("no date here", "2026-06-02") is None


def test_parse_due_year_rollover():
    assert parse_due("ready by January 5", "2026-12-15") == "2027-01-05"


def test_parse_due_invalid_dates():
    assert parse_due("done by February 30", "2026-02-01") is None
    # valid leap date whose next-year rollover does not exist
    assert parse_due("done by February 29", "2028-06-01") is None


def test_deadline_task_strips_due_phrase():
    _, _, dls, _ = extract("2026-07-01", ("Lina", "I'll publish the runbook by July 17."))
    assert dls == [{"owner": "Lina", "task": "I'll publish the runbook", "due": "2026-07-17"}]


# ── transcript parsing ───────────────────────────────────────────

def test_parse_transcript_basic():
    segments, attendees = parse_transcript(
        "Sara: Welcome everyone.\n"
        "Ahmed: I'll deliver the report by July 20.\n"
        "Sara: Thanks.\n"
    )
    assert segments == [
        {"speaker": "Sara", "text": "Welcome everyone."},
        {"speaker": "Ahmed", "text": "I'll deliver the report by July 20."},
        {"speaker": "Sara", "text": "Thanks."},
    ]
    assert attendees == ["Sara", "Ahmed"]


def test_parse_transcript_ignores_urls():
    segments, attendees = parse_transcript(
        "Sara: Welcome everyone.\n"
        "See https://example.com for the deck.\n"
        "https://example.com\n"
    )
    assert [s["speaker"] for s in segments] == ["Sara"]
    assert attendees == ["Sara"]


def test_parse_transcript_strips_timestamp_prefixes():
    segments, _ = parse_transcript(
        "[00:12:30] Ahmed: I'll deliver the report by July 20.\n"
        "(1:05) Omar: We decided to ship on Friday.\n"
        "00:42 Lina: Runbook is next.\n"
        "9:15 AM Sara: Good morning.\n"
    )
    assert [s["speaker"] for s in segments] == ["Ahmed", "Omar", "Lina", "Sara"]
    assert segments[0]["text"] == "I'll deliver the report by July 20."


def test_parse_transcript_rejects_non_speaker_lines():
    segments, _ = parse_transcript(
        "nothing usable here\n"
        "Khalid: \n"
        "A really long speaker name that goes on and on and on: hi\n"
        "\n"
    )
    assert segments == []


def test_parse_transcript_keeps_multiword_and_tight_colon():
    segments, _ = parse_transcript(
        "Dr. Anne Marie: quarterly numbers look good.\n"
        "Sara:no space after the colon\n"
    )
    assert segments == [
        {"speaker": "Dr. Anne Marie", "text": "quarterly numbers look good."},
        {"speaker": "Sara", "text": "no space after the colon"},
    ]


def test_timestamped_commitment_is_attributed_to_the_real_speaker():
    segments, _ = parse_transcript("[00:12:30] Ahmed: I'll deliver the report by July 20.")
    comms, _, _, _ = extract("2026-07-01", *[(s["speaker"], s["text"]) for s in segments])
    assert comms == [{"person": "Ahmed", "text": "Deliver the report by July 20", "due": "2026-07-20"}]
