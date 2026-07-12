# 🧠 AI Meeting Brain

**Corporate memory for every meeting, forever.**

Every meeting tool transcribes. None of them *remember*. Meeting Brain turns meeting
transcripts into permanent, structured, queryable organizational memory:

- **"What did Ahmed promise six months ago?"** → the commitment ledger answers, with quotes and dates
- **"What decisions were made about Project Atlas?"** → the decision log answers, with source meetings
- **"Which meetings mention Azure?"** → full-history topic search
- **"What deadlines are overdue?"** → the deadline radar checks every extracted date against today

## Quick start

```bash
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:8000** — the app boots with six months of realistic seeded
meeting history so every feature is demonstrable immediately.

## What it does

| Layer | Description |
|---|---|
| **Commitment Ledger** | Extracts "I'll…" statements per speaker, tracks open vs delivered, and auto-settles them when the same person later reports delivery |
| **Decision Log** | Captures "we decided / we're going with / let's go with…" with project, date, speaker, and source meeting |
| **Deadline Radar** | Parses dates ("by June 26") from conversation and flags anything overdue against today |
| **Ask Memory** | Natural-language queries with intent detection (commitments / decisions / deadlines / mentions), person resolution, and time-expression parsing ("six months ago", "last month", "in March") |
| **Full-text recall** | BM25 ranked search over every utterance ever recorded, as fallback for open-ended questions |

## Architecture

```
static/index.html   single-page UI (dashboard, ask, archive, ledgers)
app/main.py         FastAPI routes
app/engine.py       MemoryEngine — query parsing, answering, persistence
app/extract.py      commitment / decision / deadline extraction
app/search.py       tokenizer + BM25 inverted index
app/models.py       dataclasses
app/seed_data.py    6 months of demo meetings (Jan–Jul 2026)
data/store.json     persistent memory (created on first run)
```

Fully offline and deterministic — no API keys required. The extraction and ranking
layers are cleanly separated so a real pipeline (Whisper transcription, LLM answers,
vector embeddings) can be plugged in without touching the API or UI.

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/ask` | `{"query": "..."}` → answer + items + citations |
| `GET /api/meetings` · `GET /api/meetings/{id}` | archive and full transcript with extracted memory |
| `POST /api/meetings` | ingest a new transcript (`Speaker: text` lines) |
| `GET /api/commitments?person=&status=` | commitment ledger |
| `GET /api/decisions?project=` | decision log |
| `GET /api/deadlines?overdue=true` | deadline radar |
| `GET /api/stats` | dashboard aggregates |

## Adding meetings

Click **＋ New meeting** in the UI and paste a transcript, one utterance per line:

```
Ahmed: I'll deliver the report by July 20.
Sara: We decided to move the launch to September.
```

Commitments, decisions, and deadlines are extracted on ingest and become part of
permanent memory instantly.

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Tests cover the extractors, the BM25 index, the query parser, and the API, including
exact assertions on the four flagship queries (the clock is frozen in tests so
time-relative queries stay deterministic). CI runs the suite on every push.

## Roadmap

Live audio via Whisper, LLM-generated abstractive answers, hybrid vector + BM25
retrieval, calendar and Slack integrations, multi-tenant access control.
