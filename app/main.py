import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .engine import MemoryEngine
from .seed_data import MEETINGS

ROOT = Path(__file__).resolve().parent.parent
STORE = Path(os.environ.get("MEETING_BRAIN_STORE", ROOT / "data" / "store.json"))

app = FastAPI(title="AI Meeting Brain", version="1.0.0")
engine = MemoryEngine(STORE)

if not engine.meetings:
    for m in MEETINGS:
        engine.ingest(m["title"], m["date"], m["project"], m["attendees"], m["segments"])
    engine.save()


class AskRequest(BaseModel):
    query: str


class IngestRequest(BaseModel):
    title: str
    date: str
    project: str = "General"
    transcript: str


@app.get("/api/stats")
def stats():
    return engine.stats()


@app.get("/api/meetings")
def meetings():
    items = sorted(engine.meetings.values(), key=lambda m: m.date, reverse=True)
    return [engine.meeting_brief(m) for m in items]


@app.get("/api/meetings/{meeting_id}")
def meeting_detail(meeting_id: str):
    m = engine.meetings.get(meeting_id)
    if not m:
        raise HTTPException(404, "Meeting not found")
    return {
        **m.to_dict(),
        "commitments": [c.to_dict() for c in engine.commitments if c.meeting_id == meeting_id],
        "decisions": [d.to_dict() for d in engine.decisions if d.meeting_id == meeting_id],
        "deadlines": [engine.deadline_view(d) for d in engine.deadlines if d.meeting_id == meeting_id],
    }


@app.post("/api/meetings")
def ingest(req: IngestRequest):
    try:
        date.fromisoformat(req.date)
    except ValueError:
        raise HTTPException(422, "Date must be YYYY-MM-DD")
    segments, attendees = [], []
    for line in req.transcript.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        speaker, text = line.split(":", 1)
        speaker, text = speaker.strip(), text.strip()
        if not speaker or not text or len(speaker.split()) > 3:
            continue
        segments.append({"speaker": speaker, "text": text})
        if speaker not in attendees:
            attendees.append(speaker)
    if not segments:
        raise HTTPException(422, "Transcript must contain 'Speaker: text' lines")
    meeting = engine.ingest(req.title, req.date, req.project, attendees, segments)
    engine.save()
    return engine.meeting_brief(meeting)


@app.post("/api/ask")
def ask(req: AskRequest):
    if not req.query.strip():
        raise HTTPException(422, "Empty query")
    return engine.ask(req.query.strip())


@app.get("/api/commitments")
def commitments(person: str | None = None, status: str | None = None):
    items = engine.commitments
    if person:
        items = [c for c in items if c.person.lower() == person.lower()]
    if status:
        items = [c for c in items if c.status == status]
    out = []
    for c in sorted(items, key=lambda c: c.date, reverse=True):
        v = c.to_dict()
        v["meeting_title"] = engine.meetings[c.meeting_id].title
        out.append(v)
    return out


@app.get("/api/decisions")
def decisions(project: str | None = None):
    items = engine.decisions
    if project:
        items = [d for d in items if d.project.lower() == project.lower()]
    out = []
    for d in sorted(items, key=lambda d: d.date, reverse=True):
        v = d.to_dict()
        v["meeting_title"] = engine.meetings[d.meeting_id].title
        out.append(v)
    return out


@app.get("/api/deadlines")
def deadlines(overdue: bool = False):
    items = engine.deadlines
    if overdue:
        items = [d for d in items if engine.is_overdue(d)]
    return [engine.deadline_view(d) for d in sorted(items, key=lambda d: d.due)]


@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
