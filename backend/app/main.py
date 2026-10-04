"""FastAPI app: the match centre, match details, and a live stream per match."""

import asyncio
import os
from bisect import bisect_right
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.live.service import MatchdayService
from app.models.live import LiveEvent
from app.models.matchday import Matchday, MatchDetail

FRAME_INTERVAL_S = 0.25  # 4 Hz; the browser interpolates between frames
CARD_EVERY_FRAMES = 8  # score, momentum, and top moment every 2 s


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Simulating the whole matchday takes a few seconds; do it once, before serving.
    app.state.matchday = MatchdayService()
    yield


app = FastAPI(title="Match Desk API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _service(request: Request) -> MatchdayService:
    return request.app.state.matchday


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/matchday")
def matchday(request: Request) -> Matchday:
    """The match centre: every fixture, grouped by league."""
    return _service(request).matchday()


@app.get("/api/matches/{match_id}")
def match_detail(match_id: str, request: Request) -> MatchDetail:
    service = _service(request)
    if match_id not in service.by_id:
        raise HTTPException(status_code=404, detail=f"No match {match_id}")
    return service.detail(match_id)


@app.get("/api/matches/{match_id}/stream", response_class=EventSourceResponse)
async def match_stream(
    match_id: str,
    request: Request,
    frames: int | None = Query(default=None, ge=1, description="Stop after this many frames."),
) -> AsyncIterable[ServerSentEvent]:
    """Live play for one match: `frame` (positions, 4 Hz), `match_event` (each event with its
    impact, as it happens), and `card` (score, momentum, top moment, every 2 s)."""
    service = _service(request)
    if match_id not in service.by_id:
        raise HTTPException(status_code=404, detail=f"No match {match_id}")
    match = service.by_id[match_id]
    events = match.result.events
    clocks = [e.match_clock_ms for e in events]
    impacts = service.impacts[match_id]
    sent_until = service.now(match)
    tick = 0
    while frames is None or tick < frames:
        if await request.is_disconnected():
            break
        now = service.now(match)
        if now < sent_until:
            sent_until = now  # the matchday loop restarted
        for e in events[bisect_right(clocks, sent_until) : bisect_right(clocks, now)]:
            yield ServerSentEvent(
                data=LiveEvent(event=e, impact=impacts[e.event_id]),
                event="match_event",
                id=e.event_id,
            )
        sent_until = now
        yield ServerSentEvent(data=match.result.frames.frame_at(now), event="frame")
        if tick % CARD_EVERY_FRAMES == 0:
            yield ServerSentEvent(data=service.card(match_id), event="card")
        tick += 1
        await asyncio.sleep(FRAME_INTERVAL_S)
