"""Runs the agent team for a live desk, and remembers what it wrote.

The desk asks for a moment when it becomes knowable. That only happens while someone is watching,
because the desk only advances when a page or the live stream asks for it. The runner queues the
moment, runs the team (at most two moments at once), and reports every step to the desk's audit
log as it happens, then hands back the graphic.

The matchday replays identically on every loop, so each moment's run is cached on disk and
replayed with its original timings on later loops, marked "cached" in the log: the queue looks
the same, and the model is only paid for once. Delete the cache (or bump PROMPT_VERSION) to
regenerate. If the team errors or takes too long, the desk falls back to its scripted copy.
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from opentelemetry.trace import Span

from app.agents.brief import build_brief
from app.agents.team import PROMPT_VERSION, AgentTeam, Outcome
from app.agents.tracing import ended, run_span
from app.live.copy import Copy
from app.models import Claim
from app.models.proposals import AudienceBody, LocalizedText

if TYPE_CHECKING:
    from app.live.desk import AgentGraphic, ProposalDesk

log = logging.getLogger(__name__)

TEAM: list[str] = ["interpreter", "explainer", "checker", "producer", "localizer"]


class AgentRunner:
    def __init__(
        self, team: AgentTeam, cache_dir: Path, concurrency: int = 2, timeout_s: float = 50.0
    ) -> None:
        self.team = team
        self.cache_dir = cache_dir
        self.concurrency = concurrency
        self.timeout_s = timeout_s
        self.loop: asyncio.AbstractEventLoop | None = None
        self.queue: asyncio.Queue[tuple[Any, ...]] | None = None
        self.workers: list[asyncio.Task[None]] = []
        self.caches: dict[str, dict[str, Any]] = {}
        self.matchday = ""  # the simulated matchday's fingerprint (set by the app)
        # The players' stories in a match at a moment (set by the app: MatchdayService.stories).
        self.stories: Callable[[str, int], list[str]] | None = None

    def start(self) -> None:
        """Start the workers on the running event loop (call from the app's lifespan)."""
        self.loop = asyncio.get_running_loop()
        self.queue = asyncio.Queue()
        self.workers = [self.loop.create_task(self._work()) for _ in range(self.concurrency)]

    async def stop(self) -> None:
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        close = getattr(self.team, "close", None)
        if close:
            await close()

    # --- The desk's side (called from the desk, possibly on another thread) ------------------

    def request(self, desk: "ProposalDesk", candidate: Any, generation: int, queue: str) -> None:
        """Queue a moment for the team. Never blocks: the desk calls this under its lock."""
        if not self.loop or not self.queue:
            return
        brief = build_brief(
            candidate.moment_id,
            candidate.kind,
            candidate.label,
            candidate.known_ms,
            candidate.evidence_ids,
            desk.match.result.events,
            desk.ctx,
            desk.match.home,
            desk.match.away,
            candidate.copy.claims,
            self.stories(desk.match.match_id, candidate.known_ms) if self.stories else (),
        )
        job = (desk, candidate, generation, replace(brief, queue=queue))
        self.loop.call_soon_threadsafe(self.queue.put_nowait, job)

    # --- Workers -----------------------------------------------------------------------------

    async def _work(self) -> None:
        assert self.queue
        while True:
            job = await self.queue.get()
            try:
                await self._handle(*job)
            except Exception:  # never let one moment stop the workers
                log.exception("agent run failed")
            finally:
                self.queue.task_done()

    async def _handle(
        self, desk: "ProposalDesk", candidate: Any, generation: int, brief: Any
    ) -> None:
        with run_span(
            "graphics team",
            match_id=desk.match.match_id,
            moment_id=candidate.moment_id,
            moment_kind=candidate.kind,
            matchday=self.matchday,
        ) as span:
            await self._run(desk, candidate, generation, brief, span)

    async def _run(
        self, desk: "ProposalDesk", candidate: Any, generation: int, brief: Any, span: Span
    ) -> None:
        match_id = desk.match.match_id
        start = time.perf_counter()

        def step(agent: str, action: str, detail: str) -> None:
            span.add_event(f"{agent} {action}", {"detail": detail})
            desk.agent_step(candidate.index, generation, agent, action, detail)

        cached = self._cache(match_id).get(candidate.moment_id)
        if cached:
            for agent, action, detail, at_s in cached["steps"]:
                await asyncio.sleep(max(0.0, at_s - (time.perf_counter() - start)))
                step(agent, action, f"{detail} · cached")
            graphic = _graphic_from_json(cached["graphic"]) if cached["graphic"] else None
            desk.agent_result(candidate.index, generation, graphic, cached["status"])
            ended(span, cached["status"], _failure(cached["status"]), cached=True)
            return

        steps: list[tuple[str, str, str, float]] = []

        def live(agent: str, action: str, detail: str) -> None:
            steps.append((agent, action, detail, round(time.perf_counter() - start, 2)))
            step(agent, action, detail)

        try:
            outcome = await asyncio.wait_for(self.team.run(brief, live), self.timeout_s)
        except Exception as error:
            reason = "timed out" if isinstance(error, TimeoutError) else type(error).__name__
            log.warning("agent team failed on %s: %s", candidate.moment_id, error)
            desk.agent_result(candidate.index, generation, None, "error", reason)
            ended(span, "error", f"{reason}: the desk airs its scripted copy", cached=False)
            return
        graphic = to_graphic(outcome) if outcome.status == "proposed" else None
        self._remember(match_id, candidate.moment_id, outcome, graphic, steps)
        desk.agent_result(candidate.index, generation, graphic, outcome.status)
        ended(
            span,
            outcome.status,
            _failure(outcome.status),
            cached=False,
            drafts=outcome.run.drafts,
            tokens=outcome.run.tokens,
        )

    # --- Cache -------------------------------------------------------------------------------

    def _path(self, match_id: str) -> Path:
        return self.cache_dir / f"{match_id}.json"

    def _cache(self, match_id: str) -> dict[str, Any]:
        if match_id not in self.caches:
            runs: dict[str, Any] = {}
            try:
                data = json.loads(self._path(match_id).read_text())
                if (
                    data.get("version") == PROMPT_VERSION
                    and data.get("model") == self.team.model
                    and data.get("matchday") == self.matchday
                ):
                    runs = data["runs"]
            except (OSError, ValueError, KeyError):
                pass
            self.caches[match_id] = runs
        return self.caches[match_id]

    def _remember(
        self,
        match_id: str,
        moment_id: str,
        outcome: Outcome,
        graphic: "AgentGraphic | None",
        steps: list[tuple[str, str, str, float]],
    ) -> None:
        runs = self._cache(match_id)
        runs[moment_id] = {
            "status": outcome.status,
            "graphic": _graphic_to_json(graphic) if graphic else None,
            "steps": steps,
            "tokens": outcome.run.tokens,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": PROMPT_VERSION,
            "model": self.team.model,
            "matchday": self.matchday,
            "runs": runs,
        }
        self._path(match_id).write_text(json.dumps(payload, indent=1))


def _failure(status: str) -> str | None:
    """Why a finished run counts as a failure in its trace: drafts that never passed the checks."""
    if status == "failed_checks":
        return "no draft passed the checks: the desk airs its scripted copy"
    return None


def to_graphic(outcome: Outcome) -> "AgentGraphic":
    """The finished run as the desk's graphic."""
    from app.live.desk import AgentGraphic

    run = outcome.run
    assert run.draft and run.placement and run.interpretation
    v = run.localized

    def body(analyst: tuple[str, str | None], casual: tuple[str, str | None]) -> AudienceBody:
        return AudienceBody(
            analyst=LocalizedText(en=analyst[0], es=analyst[1]),
            casual=LocalizedText(en=casual[0], es=casual[1]),
        )

    if v:
        headline = body(
            (v.analyst_headline_en, v.analyst_headline_es),
            (v.casual_headline_en, v.casual_headline_es),
        )
        text = body((v.analyst_body_en, v.analyst_body_es), (v.casual_body_en, v.casual_body_es))
    else:
        headline = body((run.draft.headline, None), (run.draft.headline, None))
        text = body((run.draft.body, None), (run.draft.body, None))
    focus = run.interpretation.focus_player_id
    return AgentGraphic(
        copy=Copy(
            type=run.placement.type,
            headline=headline,
            body=text,
            claims=[
                Claim(text=c.text, evidence_event_ids=c.evidence_event_ids)
                for c in run.draft.claims
            ],
            player_id=focus if focus in run.brief.players else None,
        ),
        priority=round(run.placement.priority, 2),
        ttl_ms=run.placement.shelf_life_seconds * 1000,
        produced_by=TEAM,
    )


def _graphic_to_json(graphic: "AgentGraphic") -> dict[str, Any]:
    c = graphic.copy
    return {
        "type": c.type,
        "headline": c.headline.model_dump(),
        "body": c.body.model_dump(),
        "claims": [claim.model_dump() for claim in c.claims],
        "player_id": c.player_id,
        "priority": graphic.priority,
        "ttl_ms": graphic.ttl_ms,
        "produced_by": graphic.produced_by,
    }


def _graphic_from_json(data: dict[str, Any]) -> "AgentGraphic":
    from app.live.desk import AgentGraphic

    return AgentGraphic(
        copy=Copy(
            type=data["type"],
            headline=AudienceBody.model_validate(data["headline"]),
            body=AudienceBody.model_validate(data["body"]),
            claims=[Claim.model_validate(c) for c in data["claims"]],
            player_id=data["player_id"],
        ),
        priority=data["priority"],
        ttl_ms=data["ttl_ms"],
        produced_by=data["produced_by"],
    )
