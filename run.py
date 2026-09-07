"""Serve the demo on http://127.0.0.1:8000.

The bundled archive is a fixed corpus, so this entrypoint pins the app's clock
to the date that archive was written against. That keeps relative questions such
as "what did Ahmed promise six months ago?" landing on real meetings instead of
drifting as the calendar moves on. Export MEETING_BRAIN_TODAY to pin a different
date, or set it empty to follow the real one.
"""

import os

import uvicorn

from app.seed_data import REFERENCE_DATE

if __name__ == "__main__":
    os.environ.setdefault("MEETING_BRAIN_TODAY", REFERENCE_DATE)
    pinned = os.environ["MEETING_BRAIN_TODAY"]
    print(f"Clock: {pinned} (seeded archive)" if pinned else "Clock: today")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
