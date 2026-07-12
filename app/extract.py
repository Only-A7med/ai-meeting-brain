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

DELIVERY_RES = [
    re.compile(r"\bI(?:'ve| have)\s+(?:also\s+|finally\s+|just\s+)?(?:finished|completed|delivered|shipped|sent|published|closed out)\s+(.+)", re.I),
    re.compile(r"\bI\s+(?:also\s+|finally\s+|just\s+)?(?:finished|completed|delivered|shipped|sent|published)\s+(.+)", re.I),
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
                                "due": parse_due(sentence, meeting.date),
                            })
                        break

            due = parse_due(sentence, meeting.date)
            if due:
                deadlines.append({
                    "owner": seg.speaker,
                    "task": clean_clause(re.sub(rf"[,.]?\s*(?:by|due(?:\s+on|\s+by)?|deadline(?:\s+is)?)\s+(?:{MONTH_RE})\s+\d{{1,2}}", "", sentence, flags=re.I)),
                    "due": due,
                })
    return commitments, decisions, deadlines, deliveries
