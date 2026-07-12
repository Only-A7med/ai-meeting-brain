import json
import re
import uuid
from datetime import date, timedelta
from pathlib import Path

from .extract import MONTHS, extract_from_meeting
from .models import Commitment, Deadline, Decision, Meeting, Segment
from .search import BM25Index, tokenize

WORD_NUMS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}

INTENT_WORDS = {
    "commitment": {"promise", "promised", "promises", "commit", "committed", "commitment", "commitments"},
    "decision": {"decision", "decisions", "decided", "decide"},
    "deadline": {"deadline", "deadlines", "overdue", "due"},
    "mention": {"mention", "mentions", "mentioned", "discussed", "discuss", "covered"},
}

NOISE = {"project", "meeting", "meetings", "made", "make", "many", "list", "show", "give"}


def month_range(year, month):
    start = date(year, month, 1)
    end = (date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)) - timedelta(days=1)
    return start, end


class MemoryEngine:
    def __init__(self, store_path):
        self.store_path = Path(store_path)
        self.meetings = {}
        self.commitments = []
        self.decisions = []
        self.deadlines = []
        self.index = BM25Index()
        if self.store_path.exists():
            self._load()

    # ── persistence ──────────────────────────────────────────────

    def _load(self):
        data = json.loads(self.store_path.read_text(encoding="utf-8"))
        for m in data["meetings"]:
            meeting = Meeting(
                id=m["id"], title=m["title"], date=m["date"], project=m["project"],
                attendees=m["attendees"],
                segments=[Segment(**s) for s in m["segments"]],
            )
            self.meetings[meeting.id] = meeting
        self.commitments = [Commitment(**c) for c in data["commitments"]]
        self.decisions = [Decision(**d) for d in data["decisions"]]
        self.deadlines = [Deadline(**d) for d in data["deadlines"]]
        self._reindex()

    def save(self):
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "meetings": [m.to_dict() for m in self.meetings.values()],
            "commitments": [c.to_dict() for c in self.commitments],
            "decisions": [d.to_dict() for d in self.decisions],
            "deadlines": [d.to_dict() for d in self.deadlines],
        }
        self.store_path.write_text(json.dumps(data, indent=1), encoding="utf-8")

    def _reindex(self):
        self.index = BM25Index()
        for m in self.meetings.values():
            for i, seg in enumerate(m.segments):
                self.index.add(f"{m.id}:{i}", seg.text)

    # ── ingestion ────────────────────────────────────────────────

    def ingest(self, title, date_str, project, attendees, segments):
        meeting = Meeting(
            id=uuid.uuid4().hex[:10], title=title, date=date_str,
            project=project, attendees=attendees,
            segments=[Segment(**s) if isinstance(s, dict) else s for s in segments],
        )
        self.meetings[meeting.id] = meeting
        comms, decs, dls, deliveries = extract_from_meeting(meeting)
        for c in comms:
            self.commitments.append(Commitment(
                id=uuid.uuid4().hex[:8], meeting_id=meeting.id, person=c["person"],
                text=c["text"], date=meeting.date, due=c["due"],
            ))
        for d in decs:
            self.decisions.append(Decision(
                id=uuid.uuid4().hex[:8], meeting_id=meeting.id, project=meeting.project,
                text=d["text"], date=meeting.date, speaker=d["speaker"],
            ))
        for d in dls:
            self.deadlines.append(Deadline(
                id=uuid.uuid4().hex[:8], meeting_id=meeting.id, owner=d["owner"],
                task=d["task"], due=d["due"], date=meeting.date,
            ))
        for dv in deliveries:
            self._settle(dv["person"], dv["text"], meeting.date)
        for i, seg in enumerate(meeting.segments):
            self.index.add(f"{meeting.id}:{i}", seg.text)
        return meeting

    def _settle(self, person, delivery_text, on_date):
        dtokens = set(tokenize(delivery_text))
        for c in self.commitments:
            if c.person == person and c.status == "open" and c.date <= on_date:
                if len(dtokens & set(tokenize(c.text))) >= 2:
                    c.status = "delivered"
                    c.delivered_on = on_date
        for d in self.deadlines:
            if d.owner == person and d.status == "open" and d.date <= on_date:
                if len(dtokens & set(tokenize(d.task))) >= 2:
                    d.status = "done"

    # ── views ────────────────────────────────────────────────────

    def people(self):
        names = set()
        for m in self.meetings.values():
            names.update(m.attendees)
        return sorted(names)

    def is_overdue(self, dl):
        return dl.status == "open" and date.fromisoformat(dl.due) < date.today()

    def meeting_brief(self, m):
        return {"id": m.id, "title": m.title, "date": m.date,
                "project": m.project, "attendees": m.attendees,
                "segments_count": len(m.segments)}

    def deadline_view(self, d):
        v = d.to_dict()
        v["overdue"] = self.is_overdue(d)
        v["meeting_title"] = self.meetings[d.meeting_id].title
        return v

    def stats(self):
        today = date.today()
        dates = sorted(m.date for m in self.meetings.values())
        overdue = [d for d in self.deadlines if self.is_overdue(d)]
        upcoming = [d for d in self.deadlines
                    if d.status == "open" and date.fromisoformat(d.due) >= today]
        open_c = [c for c in self.commitments if c.status == "open"]
        return {
            "meetings": len(self.meetings),
            "first_meeting": dates[0] if dates else None,
            "last_meeting": dates[-1] if dates else None,
            "commitments_total": len(self.commitments),
            "commitments_open": len(open_c),
            "decisions": len(self.decisions),
            "deadlines_overdue": len(overdue),
            "deadlines_upcoming": len(upcoming),
            "people": self.people(),
            "projects": sorted({m.project for m in self.meetings.values()}),
        }

    # ── query understanding ──────────────────────────────────────

    def _detect_person(self, query):
        q = query.lower()
        for name in self.people():
            if re.search(rf"\b{re.escape(name.lower())}\b", q):
                return name
        return None

    def _detect_timerange(self, query):
        q, today = query.lower(), date.today()
        m = re.search(r"\b(\d+|" + "|".join(WORD_NUMS) + r")\s+months?\s+ago\b", q)
        if m:
            n = int(m.group(1)) if m.group(1).isdigit() else WORD_NUMS[m.group(1)]
            year, month0 = divmod(today.year * 12 + today.month - 1 - n, 12)
            start, end = month_range(year, month0 + 1)
            return start.isoformat(), end.isoformat(), f"around {start.strftime('%B %Y')}"
        if "last month" in q:
            prev_end = today.replace(day=1) - timedelta(days=1)
            start, end = month_range(prev_end.year, prev_end.month)
            return start.isoformat(), end.isoformat(), f"in {start.strftime('%B %Y')}"
        if "last week" in q:
            return (today - timedelta(days=7)).isoformat(), today.isoformat(), "in the last week"
        if "this year" in q:
            return date(today.year, 1, 1).isoformat(), today.isoformat(), f"in {today.year}"
        m = re.search(r"\b(?:in|back in|during|since)\s+(" + "|".join(MONTHS) + r")\b", q)
        if m:
            month = MONTHS.index(m.group(1)) + 1
            year = today.year if month <= today.month else today.year - 1
            start, end = month_range(year, month)
            return start.isoformat(), end.isoformat(), f"in {start.strftime('%B %Y')}"
        return None

    def _detect_intent(self, query):
        tokens = set(re.findall(r"[a-z']+", query.lower()))
        for intent, words in INTENT_WORDS.items():
            if tokens & words:
                return intent
        return "search"

    def _topic_tokens(self, query, person):
        skip = set()
        for words in INTENT_WORDS.values():
            skip |= words
        skip |= NOISE
        if person:
            skip.add(person.lower())
        return [t for t in tokenize(query)
                if t not in skip and t not in WORD_NUMS and not t.isdigit()
                and t not in MONTHS and t not in {"ago", "month", "months", "week", "year", "last"}]

    # ── answering ────────────────────────────────────────────────

    def ask(self, query):
        intent = self._detect_intent(query)
        person = self._detect_person(query)
        timerange = self._detect_timerange(query)
        handler = {
            "commitment": self._answer_commitments,
            "decision": self._answer_decisions,
            "deadline": self._answer_deadlines,
            "mention": self._answer_mentions,
            "search": self._answer_search,
        }[intent]
        return handler(query, person, timerange)

    def _cite(self, meeting_id, snippet=None):
        m = self.meetings[meeting_id]
        return {"meeting_id": m.id, "title": m.title, "date": m.date,
                "project": m.project, "snippet": snippet}

    def _answer_commitments(self, query, person, timerange):
        items = self.commitments
        if person:
            items = [c for c in items if c.person == person]
        label = ""
        if timerange:
            start, end, label = timerange
            items = [c for c in items if start <= c.date <= end]
        topics = self._topic_tokens(query, person)
        if topics:
            scoped = [c for c in items if set(tokenize(c.text)) & set(topics)]
            if scoped:
                items = scoped
        items = sorted(items, key=lambda c: c.date)
        who = person or "the team"
        when = f" {label}" if label else ""
        if not items:
            answer = f"No commitments found from {who}{when}."
        else:
            delivered = sum(1 for c in items if c.status == "delivered")
            answer = (f"{who} made {len(items)} commitment{'s' if len(items) != 1 else ''}{when} — "
                      f"{delivered} delivered, {len(items) - delivered} still open.")
        return {
            "intent": "commitments", "answer": answer,
            "items": [c.to_dict() for c in items],
            "citations": [self._cite(c.meeting_id, c.text) for c in items],
        }

    def _answer_decisions(self, query, person, timerange):
        items = self.decisions
        if timerange:
            start, end, _ = timerange
            items = [d for d in items if start <= d.date <= end]
        topics = self._topic_tokens(query, person)
        if topics:
            items = [d for d in items
                     if set(tokenize(d.text + " " + d.project)) & set(topics)]
        items = sorted(items, key=lambda d: d.date)
        scope = f" about \"{' '.join(topics)}\"" if topics else ""
        answer = (f"{len(items)} decision{'s' if len(items) != 1 else ''} on record{scope}."
                  if items else f"No decisions found{scope}.")
        return {
            "intent": "decisions", "answer": answer,
            "items": [d.to_dict() for d in items],
            "citations": [self._cite(d.meeting_id, d.text) for d in items],
        }

    def _answer_deadlines(self, query, person, timerange):
        only_overdue = "overdue" in query.lower()
        items = self.deadlines
        if person:
            items = [d for d in items if d.owner == person]
        if only_overdue:
            items = [d for d in items if self.is_overdue(d)]
        items = sorted(items, key=lambda d: d.due)
        if only_overdue:
            answer = (f"{len(items)} deadline{'s are' if len(items) != 1 else ' is'} overdue as of today."
                      if items else "Nothing is overdue. All deadlines are on track.")
        else:
            overdue_n = sum(1 for d in items if self.is_overdue(d))
            answer = f"{len(items)} deadlines tracked — {overdue_n} overdue."
        return {
            "intent": "deadlines", "answer": answer,
            "items": [self.deadline_view(d) for d in items],
            "citations": [self._cite(d.meeting_id, d.task) for d in items],
        }

    def _answer_mentions(self, query, person, timerange):
        topics = self._topic_tokens(query, person)
        keyword = " ".join(topics) if topics else query
        hits = {}
        for m in self.meetings.values():
            snippets = [seg.text for seg in m.segments
                        if all(re.search(rf"\b{re.escape(t)}", seg.text.lower()) for t in topics)] if topics else []
            if snippets:
                hits[m.id] = snippets
        if not hits:
            for doc_id, _score in self.index.search(keyword, k=12):
                mid, idx = doc_id.rsplit(":", 1)
                hits.setdefault(mid, []).append(self.meetings[mid].segments[int(idx)].text)
        meetings = sorted(hits, key=lambda mid: self.meetings[mid].date)
        answer = (f"\"{keyword}\" comes up in {len(meetings)} meeting{'s' if len(meetings) != 1 else ''}."
                  if meetings else f"No meetings mention \"{keyword}\".")
        return {
            "intent": "mentions", "answer": answer,
            "items": [{**self.meeting_brief(self.meetings[mid]), "matches": len(hits[mid])} for mid in meetings],
            "citations": [self._cite(mid, hits[mid][0]) for mid in meetings],
        }

    def _answer_search(self, query, person, timerange):
        results = self.index.search(query, k=8)
        citations, seen = [], set()
        for doc_id, _score in results:
            mid, idx = doc_id.rsplit(":", 1)
            if mid in seen:
                continue
            seen.add(mid)
            citations.append(self._cite(mid, self.meetings[mid].segments[int(idx)].text))
        answer = (f"Found relevant discussion in {len(citations)} meeting{'s' if len(citations) != 1 else ''}."
                  if citations else "Nothing in memory matches that query.")
        return {"intent": "search", "answer": answer, "items": [], "citations": citations}
