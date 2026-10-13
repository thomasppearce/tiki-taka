"""Runs the channel's agents for the Director (app/live/channel.py), and remembers what they wrote.

Two queues: the Director's decisions (one at a time, never behind a story) and the Watchers'
stories (two at a time). Results go back to the channel as they arrive; the channel decides
whether they're still useful (a decision that misses its countdown still upgrades the package of
the cut it was for, briefly). Like the graphics runner, every run is cached on disk, so later
loops of the matchday replay them for free, and anything that errors or times out leaves the
code-written version in place.
"""

import asyncio
import json
import logging
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from opentelemetry.trace import Span

from app.agents.channel_brief import MatchBrief
from app.agents.channel_team import CHANNEL_PROMPT_VERSION, ChannelTeam
from app.agents.schemas import CutDecision, StoryUpdate
from app.agents.tracing import ended, run_span

if TYPE_CHECKING:
    from app.live.channel import ChannelDirector

log = logging.getLogger(__name__)

CACHE_FILE = "channel.json"
CACHED_DECISION_DELAY_S = 1.5  # a cached decision still takes a moment, as a live one would
STORY_FALLBACK = "the last story stands"
DECISION_FALLBACK = "the code's pick stands"


class ChannelRunner:
    def __init__(
        self,
        team: ChannelTeam,
        cache_dir: Path,
        story_workers: int = 2,
        story_timeout_s: float = 30.0,
        decision_timeout_s: float = 15.0,
    ) -> None:
        self.team = team
        self.cache_dir = cache_dir
        self.story_workers = story_workers
        self.story_timeout_s = story_timeout_s
        self.decision_timeout_s = decision_timeout_s
        self.loop: asyncio.AbstractEventLoop | None = None
        self.stories: asyncio.Queue[tuple[Any, ...]] | None = None
        self.decisions: asyncio.Queue[tuple[Any, ...]] | None = None
        self.workers: list[asyncio.Task[None]] = []
        self.cache: dict[str, Any] | None = None
        self.matchday = ""  # the simulated matchday's fingerprint (set by the app)

    def start(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.stories, self.decisions = asyncio.Queue(), asyncio.Queue()
        self.workers = [
            self.loop.create_task(self._work(self.decisions, self._decide)),
            *(
                self.loop.create_task(self._work(self.stories, self._story))
                for _ in range(self.story_workers)
            ),
        ]

    async def stop(self) -> None:
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)

    # --- The channel's side (called under the channel's lock; never blocks) -----------------

    def request_story(
        self, channel: "ChannelDirector", match_id: str, key: str, brief: MatchBrief
    ) -> None:
        if self.loop and self.stories:
            job = (channel, match_id, key, brief)
            self.loop.call_soon_threadsafe(self.stories.put_nowait, job)

    def request_decision(
        self,
        channel: "ChannelDirector",
        key: str,
        reason: str,
        on_air: str,
        briefs: Sequence[MatchBrief],
    ) -> None:
        if self.loop and self.decisions:
            job = (channel, key, reason, on_air, tuple(briefs))
            self.loop.call_soon_threadsafe(self.decisions.put_nowait, job)

    # --- Workers -----------------------------------------------------------------------------

    @staticmethod
    async def _work(queue: "asyncio.Queue[tuple[Any, ...]]", handle: Any) -> None:
        while True:
            job = await queue.get()
            try:
                await handle(*job)
            except Exception:  # one bad run never stops the workers
                log.exception("channel agent run failed")
            finally:
                queue.task_done()

    async def _story(
        self, channel: "ChannelDirector", match_id: str, key: str, brief: MatchBrief
    ) -> None:
        with run_span("watcher", match_id=match_id, key=key, matchday=self.matchday) as span:
            cached = self._cached(f"story:{key}")
            if cached:
                update = StoryUpdate.model_validate(cached["value"]) if cached["value"] else None
                self._story_result(channel, match_id, key, update, cached, cached=True)
                _ended(span, cached, cached=True, fallback=STORY_FALLBACK)
                return
            start = time.perf_counter()
            try:
                update, tokens, problems, sent_back = await asyncio.wait_for(
                    self.team.story(brief), self.story_timeout_s
                )
            except Exception as error:
                reason = "timed out" if isinstance(error, TimeoutError) else type(error).__name__
                channel.story_failed(match_id, key, reason)
                ended(span, "error", f"{reason}: {STORY_FALLBACK}", cached=False)
                return
            run = self._remember(f"story:{key}", update, problems, sent_back, start, tokens)
            self._story_result(channel, match_id, key, update, run, cached=False)
            _ended(span, run, cached=False, fallback=STORY_FALLBACK)

    def _story_result(
        self,
        channel: "ChannelDirector",
        match_id: str,
        key: str,
        update: StoryUpdate | None,
        run: dict[str, Any],
        cached: bool,
    ) -> None:
        if update is None:
            channel.story_failed(match_id, key, f"checker: {run['problems'][0]}")
        else:
            channel.story_ready(
                match_id,
                key,
                update,
                run["seconds"],
                run["tokens"],
                cached,
                sent_back=run.get("sent_back", []),
            )

    async def _decide(
        self,
        channel: "ChannelDirector",
        key: str,
        reason: str,
        on_air: str,
        briefs: tuple[MatchBrief, ...],
    ) -> None:
        with run_span(
            "director",
            key=key,
            reason=reason,
            on_air=on_air,
            candidates=[b.match_id for b in briefs],
            matchday=self.matchday,
        ) as span:
            cached = self._cached(f"decision:{key}")
            if cached:
                await asyncio.sleep(min(CACHED_DECISION_DELAY_S, cached["seconds"]))
                decision = CutDecision.model_validate(cached["value"]) if cached["value"] else None
                self._decision_result(channel, key, decision, cached, cached=True)
                _ended(span, cached, cached=True, fallback=DECISION_FALLBACK)
                return
            start = time.perf_counter()
            try:
                decision, tokens, problems, sent_back = await asyncio.wait_for(
                    self.team.decide(reason, on_air, briefs), self.decision_timeout_s
                )
            except Exception as error:
                why = "timed out" if isinstance(error, TimeoutError) else type(error).__name__
                channel.decision_failed(key, why)
                ended(span, "error", f"{why}: {DECISION_FALLBACK}", cached=False)
                return
            run = self._remember(f"decision:{key}", decision, problems, sent_back, start, tokens)
            self._decision_result(channel, key, decision, run, cached=False)
            _ended(span, run, cached=False, fallback=DECISION_FALLBACK)

    def _decision_result(
        self,
        channel: "ChannelDirector",
        key: str,
        decision: CutDecision | None,
        run: dict[str, Any],
        cached: bool,
    ) -> None:
        if decision is None:
            channel.decision_failed(key, f"checker: {run['problems'][0]}")
        else:
            channel.decision_ready(
                key,
                decision,
                run["seconds"],
                run["tokens"],
                cached,
                sent_back=run.get("sent_back", []),
            )

    # --- Cache -------------------------------------------------------------------------------

    def _runs(self) -> dict[str, Any]:
        if self.cache is None:
            self.cache = {}
            try:
                data = json.loads((self.cache_dir / CACHE_FILE).read_text())
                if (
                    data.get("version") == CHANNEL_PROMPT_VERSION
                    and data.get("model") == self.team.model
                    and data.get("matchday") == self.matchday
                ):
                    self.cache = data["runs"]
            except (OSError, ValueError, KeyError):
                pass
        return self.cache

    def _cached(self, key: str) -> dict[str, Any] | None:
        run: dict[str, Any] | None = self._runs().get(key)
        return run

    def _remember(
        self,
        key: str,
        value: StoryUpdate | CutDecision | None,
        problems: list[str],
        sent_back: list[str],
        start: float,
        tokens: int,
    ) -> dict[str, Any]:
        run = {
            "value": value.model_dump() if value else None,
            "problems": problems,
            "sent_back": sent_back,
            "seconds": round(time.perf_counter() - start, 2),
            "tokens": tokens,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        runs = self._runs()
        runs[key] = run
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CHANNEL_PROMPT_VERSION,
            "model": self.team.model,
            "matchday": self.matchday,
            "runs": runs,
        }
        (self.cache_dir / CACHE_FILE).write_text(json.dumps(payload, indent=1))
        return run


def _ended(span: Span, run: dict[str, Any], cached: bool, fallback: str) -> None:
    """How a story or decision ended: each send-back to redraft is an event on the span; a run
    whose last draft still failed the checks counts as a failure."""
    for why in run.get("sent_back", []):
        span.add_event("sent back by the checker", {"reason": why})
    passed = run["value"] is not None
    ended(
        span,
        "ready" if passed else "failed_checks",
        None if passed else f"checker: {run['problems'][0]}: {fallback}",
        cached=cached,
        seconds=run["seconds"],
        tokens=run["tokens"],
        sent_back=len(run.get("sent_back", [])),
    )
