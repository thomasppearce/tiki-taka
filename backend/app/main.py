"""FastAPI app: the match centre, match details, the proposal desk, and a live stream per match."""

import asyncio
import os
from bisect import bisect_right
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.generator.matchday import ScheduledMatch
from app.live.service import MatchdayService
from app.models import MatchEvent, OverlayCommand
from app.models.desk import ApproveRequest, Desk
from app.models.live import LiveEvent
from app.models.matchday import Matchday, MatchDetail

FRAME_INTERVAL_S = 0.25  # 4 Hz; the browser interpolates between frames
CARD_EVERY_FRAMES = 8  # score, momentum, and top moment every 2 s
MAX_EVENT_IDS = 200


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


def _match(service: MatchdayService, match_id: str) -> ScheduledMatch:
    if match_id not in service.by_id:
        raise HTTPException(status_code=404, detail=f"No match {match_id}")
    return service.by_id[match_id]


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
    _match(service, match_id)
    return service.detail(match_id)


@app.get("/api/matches/{match_id}/events")
def match_events(
    match_id: str,
    request: Request,
    ids: str = Query(max_length=8_000, description="Comma-separated event ids, at most 200."),
) -> list[MatchEvent]:
    """Specific events by id (the receipts a proposal or key moment cites), never ones that have
    not happened yet."""
    service = _service(request)
    match = _match(service, match_id)
    wanted = set(ids.split(",")[:MAX_EVENT_IDS])
    now = service.now(match)
    return [e for e in match.result.events if e.event_id in wanted and e.match_clock_ms <= now]


@app.get("/api/matches/{match_id}/desk")
def match_desk(match_id: str, request: Request) -> Desk:
    """The producer's desk: pending proposals, what is on air, and the audit log."""
    service = _service(request)
    _match(service, match_id)
    return service.desk(match_id)


@app.post("/api/matches/{match_id}/proposals/{proposal_id}/approve")
def approve_proposal(
    match_id: str, proposal_id: str, body: ApproveRequest, request: Request
) -> Desk:
    """Put a proposal on air, optionally with edited copy for one feed. Returns the new desk."""
    service = _service(request)
    match = _match(service, match_id)
    try:
        service.desks[match_id].approve(proposal_id, body, service.now(match))
    except KeyError:
        raise HTTPException(status_code=409, detail=f"{proposal_id} is not pending") from None
    return service.desk(match_id)


@app.post("/api/matches/{match_id}/proposals/{proposal_id}/reject")
def reject_proposal(match_id: str, proposal_id: str, request: Request) -> Desk:
    service = _service(request)
    match = _match(service, match_id)
    try:
        service.desks[match_id].reject(proposal_id, service.now(match))
    except KeyError:
        raise HTTPException(status_code=409, detail=f"{proposal_id} is not pending") from None
    return service.desk(match_id)


@app.get("/api/matches/{match_id}/overlays")
def match_overlays(
    match_id: str, request: Request, profile_id: str = "feed_analyst_en"
) -> list[OverlayCommand]:
    """Every graphic aired so far, as timed, machine-readable overlay commands for one feed."""
    service = _service(request)
    match = _match(service, match_id)
    try:
        return service.desks[match_id].overlays(profile_id, service.now(match))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No feed profile {profile_id}") from None


@app.get("/api/matches/{match_id}/stream", response_class=EventSourceResponse)
async def match_stream(
    match_id: str,
    request: Request,
    frames: int | None = Query(default=None, ge=1, description="Stop after this many frames."),
) -> AsyncIterable[ServerSentEvent]:
    """Live play for one match: `frame` (positions, 4 Hz), `match_event` (each event with its
    impact, as it happens), `card` (score, momentum, top moment, every 2 s), and `desk` (the
    proposal desk, whenever it changes)."""
    service = _service(request)
    match = _match(service, match_id)
    desk = service.desks[match_id]
    desk_version = -1
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
        desk.sync(now)
        if desk.state.version != desk_version:
            snapshot = desk.snapshot(now)
            desk_version = snapshot.version
            yield ServerSentEvent(data=snapshot, event="desk")
        tick += 1
        await asyncio.sleep(FRAME_INTERVAL_S)
