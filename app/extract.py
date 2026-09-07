import re
from datetime import date, timedelta

MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]
MONTH_RE = "|".join(m.capitalize() for m in MONTHS)

COMMITMENT_RES = [
    re.compile(r"\bI(?:'ll| will|'m going to| am going to)\s+(.+)", re.I),
    re.compile(r"\bI can take (?:care of |on )?(.+)", re.I),
    re.compile(r"\bleave (?:that|it|this) with me[,;]?\s*(.+)", re.I),
]

ADVERB = r"(?:also\s+|finally\s+|just\s+)?"
DELIVERED = r"(?:finished|completed|delivered|shipped|sent|published|closed out)"

DELIVERY_RES = [
    re.compile(rf"\bI(?:'ve| have)\s+{ADVERB}{DELIVERED}\s+(.+)", re.I),
    re.compile(rf"\bI\s+{ADVERB}{DELIVERED}\s+(.+)", re.I),
]

DECISION_RES = [
    re.compile(r"\bwe(?:'ve| have)?\s*(?:formally\s+)?decided(?:\s+(?:to|on|that))?\s+(.+)", re.I),
    re.compile(r"\bwe agreed(?:\s+(?:to|on|that))?\s+(.+)", re.I),
    re.compile(r"\bwe're going with\s+(.+)", re.I),
    re.compile(r"\blet's go with\s+(.+)", re.I),
    re.compile(r"\b(?:final call|decision)\s*:\s*(.+)", re.I),
]

DUE_RES = [
    re.compile(rf"\bby\s+({MONTH_RE})\s+(\d{{1,2}})\b", re.I),
    re.compile(rf"\bdue\s+(?:on\s+|by\s+)?({MONTH_RE})\s+(\d{{1,2}})\b", re.I),
    re.compile(rf"\bdeadline\s+(?:is\s+)?({MONTH_RE})\s+(\d{{1,2}})\b", re.I),
]

# Removes the "by June 26" tail so a deadline's task reads as a task.
DUE_PHRASE_RE = re.compile(
    rf"[,.]?\s*(?:by|due(?:\s+on|\s+by)?|deadline(?:\s+is)?)\s+(?:{MONTH_RE})\s+\d{{1,2}}",
    re.I,
)

# A transcript line is "Speaker: text", where the speaker is one to three words
# each starting with a letter. The lookahead rejects the "//" of a URL, so
# "See https://example.com" is not read as a speaker named "See https".
SPEAKER_LINE_RE = re.compile(
    r"^(?P<speaker>[^\W\d_][\w.'\-]*(?:[ \t]+[^\W\d_][\w.'\-]*){0,2}):(?!//)[ \t]*(?P<text>\S.*)$"
)

# Exporters prefix lines with a timestamp — "[00:12:30] Ahmed: …", "(1:05) …",
# "00:12 …" — which would otherwise swallow the real speaker.
TIMESTAMP_PREFIX_RE = re.compile(
    r"^[\[(]?\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?(?:\s*[AaPp]\.?[Mm]\.?)?[\])]?\s+"
)

MAX_SPEAKER_LEN = 40


def split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def clean_clause(clause):
    clause = clause.strip().rstrip(".!?,;")
    return clause[0].upper() + clause[1:] if clause else clause


def parse_due(sentence, meeting_date):
    for rx in DUE_RES:
        m = rx.search(sentence)
        if m:
            month = MONTHS.index(m.group(1).lower()) + 1
            day = int(m.group(2))
            mdate = date.fromisoformat(meeting_date)
            try:
                due = date(mdate.year, month, day)
                if due < mdate - timedelta(days=30):
                    due = date(mdate.year + 1, month, day)
            except ValueError:
                continue
            return due.isoformat()
    return None


def extract_from_meeting(meeting):
    commitments, decisions, deadlines, deliveries = [], [], [], []
    for seg in meeting.segments:
        for sentence in split_sentences(seg.text):
            matched_delivery = False
            for rx in DELIVERY_RES:
                m = rx.search(sentence)
                if m:
                    deliveries.append({"person": seg.speaker, "text": clean_clause(m.group(1))})
                    matched_delivery = True
                    break
            if matched_delivery:
                continue

            due = parse_due(sentence, meeting.date)

            for rx in DECISION_RES:
                m = rx.search(sentence)
                if m:
                    decisions.append({
                        "speaker": seg.speaker,
                        "text": clean_clause(m.group(1)),
                    })
                    break
            else:
                for rx in COMMITMENT_RES:
                    m = rx.search(sentence)
                    if m:
                        clause = clean_clause(m.group(1))
                        if len(clause.split()) >= 3:
                            commitments.append({
                                "person": seg.speaker,
                                "text": clause,
                                "due": due,
                            })
                        break

            if due:
                deadlines.append({
                    "owner": seg.speaker,
                    "task": clean_clause(DUE_PHRASE_RE.sub("", sentence)),
                    "due": due,
                })
    return commitments, decisions, deadlines, deliveries


def parse_transcript(text):
    """Parse "Speaker: text" lines into segments plus the speakers, in order."""
    segments, attendees = [], []
    for raw in text.splitlines():
        line = TIMESTAMP_PREFIX_RE.sub("", raw.strip(), count=1)
        m = SPEAKER_LINE_RE.match(line)
        if not m:
            continue
        speaker = " ".join(m.group("speaker").split())
        if len(speaker) > MAX_SPEAKER_LEN:
            continue
        segments.append({"speaker": speaker, "text": m.group("text").strip()})
        if speaker not in attendees:
            attendees.append(speaker)
    return segments, attendees
