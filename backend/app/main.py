"""FastAPI app: REST endpoints and the live SSE stream for the control room."""

import asyncio
import os
from collections.abc import AsyncIterable
from itertools import islice

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.generator.fake import fake_events

app = FastAPI(title="Match Desk API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/stream/events", response_class=EventSourceResponse)
async def stream_events(
    seed: int = 7,
    interval_ms: int = Query(default=800, ge=0, le=10_000, description="Wall-clock gap per event."),
    limit: int | None = Query(default=None, ge=1, description="Stop after this many events."),
) -> AsyncIterable[ServerSentEvent]:
    """Stream match events as `match_event` SSE messages (Phase 0: fake events)."""
    for event in islice(fake_events(seed), limit):
        yield ServerSentEvent(data=event, event="match_event", id=event.event_id)
        await asyncio.sleep(interval_ms / 1000)
