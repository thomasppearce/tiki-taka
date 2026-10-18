"""FastAPI app: the match centre, match details, the proposal desk, and a live stream per match."""

import asyncio
import os
from bisect import bisect_right
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.agents.channel_runner import ChannelRunner
from app.agents.channel_team import ChannelTeam, channel_intro
from app.agents.drill import DRILL
from app.agents.recap import RecapWriter
from app.agents.runner import AgentRunner
from app.agents.team import AgentTeam
from app.agents.tracing import start_tracing
from app.generator.matchday import ScheduledMatch
from app.live.channel import ChannelDirector
from app.live.recap import RecapDesk
from app.live.service import MatchdayService
from app.models import MatchEvent, OverlayCommand
from app.models.channel import (
    Channel,
    ClockRequest,
    HoldRequest,
    PinRequest,
    Squads,
    TakeRequest,
)
from app.models.desk import ApproveRequest, Desk
from app.models.drill import DrillRequest, DrillState
from app.models.live import LiveEvent
from app.models.matchday import Matchday, MatchDetail
from app.models.recap import MatchRecap, Recap
from app.models.replay import Replay
from app.models.table import LeagueTable

FRAME_INTERVAL_S = 0.25  # 4 Hz; the browser interpolates between frames
CARD_EVERY_FRAMES = 8  # score, momentum, and top moment every 2 s
CHANNEL_INTERVAL_S = 0.5  # the channel stream checks for a new cut twice a second,
SIGNALS_EVERY_TICKS = 4  # sends every match's signals every 2 s,
TABLE_EVERY_TICKS = 10  # and the table every 5 s
MAX_EVENT_IDS = 200


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    load_dotenv()  # Agent Framework doesn't load .env by itself
    # The agent team runs on Microsoft Foundry when a project is configured (backend/.env);
    # otherwise, and in tests (TIKITAKA_AGENTS=off), every match uses the scripted producer.
    runner: AgentRunner | None = None
    channel: ChannelRunner | None = None
    writer: RecapWriter | None = None
    cache: Path | None = None
    if os.environ.get("FOUNDRY_PROJECT_ENDPOINT") and os.environ.get("TIKITAKA_AGENTS") != "off":
        cache = Path(os.environ.get("TIKITAKA_AGENT_CACHE", ".cache/agent-runs"))
        team = AgentTeam.from_env()
        await start_tracing(team.client)  # every agent run as a trace in Foundry
        await team.connect()  # the knowledge base over MCP, when AI Search is configured
        runner = AgentRunner(team, cache_dir=cache)
        runner.start()
        # The channel's Director shares the team's fast deployment; the Watchers, with no
        # deadline, use the more accurate one when it is configured (FOUNDRY_WATCHER_MODEL).
        watchers = AgentTeam.from_env("FOUNDRY_WATCHER_MODEL", knowledge=False)
        channel = ChannelRunner(ChannelTeam(team, watchers), cache_dir=cache)
        channel.start()
        # Recaps have no deadline either: the accurate model writes them and checks them.
        writer = RecapWriter(watchers, watchers)
    app.state.agents = runner
    # Simulating the whole matchday takes a few seconds; do it once, before serving.
    service = MatchdayService(agents=runner)
    service.channel.agents = channel
    if channel:  # the channel's agents know which matchday they're covering
        channel.team.intro = channel_intro(service.matchday_number, service.last_matchday)
    # Cached agent runs are only reused for the same simulated matchday.
    for cached in (runner, channel):
        if cached:
            cached.matchday = service.fingerprint
    if runner:
        runner.stories = service.stories  # the graphics team knows the players' stories too
    app.state.matchday = service
    app.state.recap = RecapDesk(service, writer, channel.team if channel else None, cache)
    app.state.recap.start()
    yield
    if channel:
        await channel.stop()
    if runner:
        await runner.stop()


app = FastAPI(title="Tiki-Taka API", version="0.3.0", lifespan=lifespan)

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
def health(request: Request) -> dict[str, str]:
    """Up, who writes the featured match's proposals (the agent team or the script), and which
    simulated matchday this is (the same everywhere: app/detmath.py)."""
    runner: AgentRunner | None = request.app.state.agents
    matchday = _service(request).fingerprint
    if runner:
        model = os.environ.get("FOUNDRY_MODEL_LABEL", runner.team.model)
        return {"status": "ok", "agents": "foundry", "model": model, "matchday": matchday}
    return {"status": "ok", "agents": "scripted", "matchday": matchday}


@app.get("/api/matchday")
def matchday(request: Request) -> Matchday:
    """The match centre: every fixture, grouped by league."""
    return _service(request).matchday()


@app.get("/api/table")
def league_table(request: Request) -> LeagueTable:
    """The league as it stands, every zone change so far today, and what a goal in each live
    match would change."""
    return _service(request).table()


LENS = Query(
    default=None,
    description="Whose whip-around: none for the channel, `club:<club_id>` for a fan's club, or "
    "`xi:<11 player ids, comma-separated>` for a fan's fantasy XI.",
)


def _whip(service: MatchdayService, lens: str | None) -> ChannelDirector:
    try:
        return service.whip(lens)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None


@app.get("/api/channel")
def channel(request: Request, lens: str | None = LENS) -> Channel:
    """The whip-around: the match on air, the Director's next cut, and every match's signals."""
    service = _service(request)
    return _whip(service, lens).snapshot(service.clock.clock_ms())


@app.post("/api/channel/take")
def channel_take(body: TakeRequest, request: Request, lens: str | None = LENS) -> Channel:
    """Take the pending cut now, or cut straight to a match."""
    service = _service(request)
    whip = _whip(service, lens)
    try:
        whip.take(service.clock.clock_ms(), body.match_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No match {body.match_id}") from None
    return whip.snapshot(service.clock.clock_ms())


@app.post("/api/channel/hold")
def channel_hold(body: HoldRequest, request: Request, lens: str | None = LENS) -> Channel:
    """Pause or resume the Director's automatic cuts."""
    service = _service(request)
    whip = _whip(service, lens)
    whip.hold(service.clock.clock_ms(), body.held)
    return whip.snapshot(service.clock.clock_ms())


@app.post("/api/channel/pin")
def channel_pin(body: PinRequest, request: Request, lens: str | None = LENS) -> Channel:
    """Fix the feed on a match (cutting to it), or release it (no match_id)."""
    service = _service(request)
    whip = _whip(service, lens)
    try:
        whip.pin(service.clock.clock_ms(), body.match_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No match {body.match_id}") from None
    return whip.snapshot(service.clock.clock_ms())


@app.get("/api/squads")
def squads(request: Request) -> Squads:
    """Every player in the league, the team of the season, and how fantasy points are scored."""
    return _service(request).squads()


@app.get("/api/channel/stream", response_class=EventSourceResponse)
async def channel_stream(
    request: Request,
    lens: str | None = LENS,
    ticks: int | None = Query(default=None, ge=1, description="Stop after this many ticks."),
) -> AsyncIterable[ServerSentEvent]:
    """The whip-around live: `channel` whenever the feed cuts or a cut is proposed, `signals`
    (every live match's pressure and stakes) and, on a fan's whip-around, `lens` (their club or
    their XI's live points) every 2 s, and `table` (the league as it stands) every 5 s. Pages
    follow the match on air through its own stream."""
    service = _service(request)
    whip = _whip(service, lens)
    version = -1
    tick = 0
    while ticks is None or tick < ticks:
        if await request.is_disconnected():
            break
        snapshot = whip.snapshot(service.clock.clock_ms())
        if snapshot.version != version:
            version = snapshot.version
            yield ServerSentEvent(data=snapshot, event="channel")
        elif tick % SIGNALS_EVERY_TICKS == 0:
            yield ServerSentEvent(data=snapshot.signals, event="signals")
            if snapshot.lens.kind != "channel":
                yield ServerSentEvent(data=snapshot.lens, event="lens")
        if tick % TABLE_EVERY_TICKS == 0:
            yield ServerSentEvent(data=service.table(), event="table")
        tick += 1
        await asyncio.sleep(CHANNEL_INTERVAL_S)


@app.get("/api/recap")
def recap(request: Request, ended: bool = False) -> Recap:
    """How the matchday unfolded, once its last match ends: where it left the table, worked out
    by code, and the story, written by the recap writer and checked (app/live/recap.py).
    `ended`: the finished day whatever the clock says (the /recap page)."""
    return request.app.state.recap.snapshot(_service(request).clock.clock_ms(), ended)


@app.get("/api/recaps")
def match_recaps(request: Request, ended: bool = False) -> list[MatchRecap]:
    """Every match's recap (pending until its final whistle), in fixture order."""
    service = _service(request)
    now = service.clock.clock_ms()
    return [request.app.state.recap.match(m.match_id, now, ended) for m in service.matches]


@app.get("/api/matches/{match_id}/recap")
def match_recap(match_id: str, request: Request, ended: bool = False) -> MatchRecap:
    """A match's recap at its final whistle, written by its Watcher and checked."""
    service = _service(request)
    _match(service, match_id)
    return request.app.state.recap.match(match_id, service.clock.clock_ms(), ended)


@app.post("/api/clock")
def move_clock(body: ClockRequest, request: Request) -> dict[str, int]:
    """A demo control: move the matchday clock to a minute, or (no minute) to just after the
    day's last final whistle. One clock: everyone watching moves with it."""
    service = _service(request)
    # Minutes played, as MATCH_START_MINUTE counts them: "55" is where a cold start begins, so
    # a session from there replays the agents' cached runs.
    target = service.over_ms + 2_000 if body.minute is None else round(body.minute * 60_000)
    if target >= service.clock.cycle_ms:
        raise HTTPException(status_code=422, detail="past the end of the matchday")
    service.jump(target)
    return {"clock_ms": service.clock.clock_ms()}


@app.get("/api/drill")
def drill() -> DrillState:
    """The failure drill now: which agent is failing on purpose, and how (app/agents/drill.py)."""
    return DRILL.state()


@app.post("/api/drill")
def start_drill(body: DrillRequest) -> DrillState:
    """Make an agent fail on purpose: `blip` fails its next model call once (the retry recovers
    it); `down` fails every call for three minutes (the system falls back)."""
    DRILL.start(body.agent, body.mode)
    return DRILL.state()


@app.post("/api/drill/end")
def end_drill() -> DrillState:
    DRILL.end()
    return DRILL.state()


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


@app.get("/api/matches/{match_id}/replays/{event_id}")
def match_replay(match_id: str, event_id: str, request: Request) -> Replay:
    """The move behind a goal or a shot that has already happened: frames every 250 ms and the
    events, with the shot marked for slow motion."""
    service = _service(request)
    _match(service, match_id)
    replay = service.replay(match_id, event_id)
    if replay is None:
        raise HTTPException(status_code=404, detail=f"No replay for {event_id}")
    return replay


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
    producer: bool = Query(default=False, description="The control room: a producer is in."),
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
        if producer:
            desk.attend()
        desk.sync(now)
        if desk.state.version != desk_version:
            snapshot = desk.snapshot(now)
            desk_version = snapshot.version
            yield ServerSentEvent(data=snapshot, event="desk")
        tick += 1
        await asyncio.sleep(FRAME_INTERVAL_S)
