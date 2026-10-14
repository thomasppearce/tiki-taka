"""How the final day unfolded: the facts, written by code, and the recap built on them.

Once the last match ends, the recap writer (app/agents/recap.py) tells the day's story from these
facts, and every beat cites them by id:
- the outcomes: the title, the top four, the relegation places, the Golden Boot, and the last
  goal to change each race (`final:champions`, `final:top_four`, `final:relegated`,
  `final:golden_boot`, `final:deciders`);
- every goal that moved a club into or out of a zone, or changed the top of the Golden Boot race
  (`<match_id>:<event_id>`: event ids are only unique within a match);
- each match's final score (`ft:<match_id>`).
The recap is written once per matchday and cached like the other agent runs. If the writer fails
its checks, or the agents are off, code writes the recap from the same facts.
"""

import asyncio
import json
import logging
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.agents.drill import failure_reason
from app.agents.tracing import ended, run_span
from app.models.recap import Recap, RecapBeat, RecapFact
from app.models.table import LeagueTable
from app.state.table import _ordinal

if TYPE_CHECKING:
    from app.agents.recap import RecapWriter
    from app.live.service import MatchdayService

log = logging.getLogger(__name__)

CACHE_FILE = "recap.json"


def day_facts(service: "MatchdayService") -> list[RecapFact]:
    """Everything the recap may say, as of the final whistle, each with an id to cite."""
    table = service.table_at(service.over_ms)
    return [*_outcomes(service, table), *_moments(service, table), *_results(service)]


def _outcomes(service: "MatchdayService", table: LeagueTable) -> list[RecapFact]:
    rows = table.rows
    first, second = rows[0], rows[1]
    gap = first.points - second.points
    margin = "on goal difference" if gap == 0 else f"by {_count(gap, 'point')}"
    champions = (
        f"{first.club.name} are champions {margin}, on {first.points} points; they started the "
        f"day {_ordinal(first.start_position)}. {second.club.name} finish 2nd on "
        f"{second.points} points, having started {_ordinal(second.start_position)}."
    )
    top = [r for r in rows if r.position <= 4]
    climbed = [r for r in top if r.start_position > 4]
    dropped = [r for r in rows if r.position > 4 and r.start_position <= 4]
    top_four = (
        f"The top four: {_names(r.club.name for r in top)}."
        + "".join(f" {r.club.name} climb in from {_ordinal(r.start_position)}." for r in climbed)
        + "".join(
            f" {r.club.name} drop out, from {_ordinal(r.start_position)} to {_ordinal(r.position)}."
            for r in dropped
        )
    )
    down = [r for r in rows if r.zone == "relegation"]
    dipped = {c.club_id for s in table.swings for c in s.changes if c.to_zone == "relegation"}
    survived = [r for r in rows if r.club.club_id in dipped and r.zone != "relegation"]
    relegated = f"Relegated: {_names(r.club.name for r in down)}." + "".join(
        f" {r.club.name} stay up in {_ordinal(r.position)}, after time in the relegation zone "
        "today."
        for r in survived
    )
    boot = table.golden_boot.rows
    leaders = [s for s in boot if s.position == 1]
    chasers = [s for s in boot if s.position > 1][:2]
    golden = (
        "The Golden Boot: "
        + _names(f"{s.name} ({s.club.name})" for s in leaders)
        + f", {leaders[0].goals} league goals"
        + (f", {leaders[0].today} of them today" if len(leaders) == 1 and leaders[0].today else "")
        + ". Next: "
        + "; ".join(f"{s.name} {s.goals}" for s in chasers)
        + "."
    )
    return [
        RecapFact(fact_id="final:champions", text=champions),
        RecapFact(fact_id="final:top_four", text=top_four),
        RecapFact(fact_id="final:relegated", text=relegated),
        RecapFact(fact_id="final:golden_boot", text=golden),
        RecapFact(fact_id="final:deciders", text=_deciders(service, table)),
    ]


def _deciders(service: "MatchdayService", table: LeagueTable) -> str:
    """The last goal that changed each race: so "one goal settled two races" is a fact the
    recap can cite, not a reading of its own."""

    def race(change: Any) -> str:
        zones = {change.from_zone, change.to_zone}
        if "champions" in zones:
            return "the title"
        if "relegation" in zones:
            return "the drop"
        return "the top four"

    last: dict[str, tuple[int, str, str]] = {}
    for swing in table.swings:
        for change in swing.changes:
            last[race(change)] = (swing.match_clock_ms, swing.match_id, swing.event_id)
    for boot in table.golden_boot.swings:
        last["the Golden Boot"] = (boot.match_clock_ms, boot.match_id, boot.event_id)

    def scorer(match_id: str, event_id: str) -> str:
        event = next(e for e in service.by_id[match_id].result.events if e.event_id == event_id)
        player, club = service.fantasy.players[event.player_id or ""]
        return f"{player.name} for {club.name}"

    parts = []
    for name in ("the title", "the top four", "the drop", "the Golden Boot"):
        if name in last:
            clock, match_id, event_id = last[name]
            parts.append(f"{name} at {clock // 60_000 + 1}' ({scorer(match_id, event_id)})")
        else:
            parts.append(f"{name}: no goal changed it today")
    return (
        "The last goal to change each race: "
        + "; ".join(parts)
        + ". No later goal changed those races."
    )


def _moments(service: "MatchdayService", table: LeagueTable) -> list[RecapFact]:
    """Each goal that moved the table or the top of the Golden Boot race, in time order."""
    # Event ids are unique within a match, so a goal is its match and its event.
    swings = {(s.match_id, s.event_id): s.summary for s in table.swings}
    boot = {(s.match_id, s.event_id): s.summary for s in table.golden_boot.swings}
    facts = []
    for match_id, event in sorted(
        (
            (m.match_id, e)
            for m in service.matches
            for e in m.result.events
            if e.type == "goal"
            and ((m.match_id, e.event_id) in swings or (m.match_id, e.event_id) in boot)
        ),
        key=lambda x: x[1].match_clock_ms,
    ):
        m = service.by_id[match_id]
        home, away = m.result.score_at(event.match_clock_ms)
        player, club = service.fantasy.players[event.player_id or ""]
        minute = event.match_clock_ms // 60_000 + 1
        key = (match_id, event.event_id)
        said = " ".join(x for x in (swings.get(key), boot.get(key)) if x)
        facts.append(
            RecapFact(
                fact_id=f"{match_id}:{event.event_id}",
                minute=minute,
                match_id=match_id,
                text=(
                    f"{minute}' {player.name} scores for {club.name}: {m.home.name} {home}-{away} "
                    f"{m.away.name}. {said}"
                ),
            )
        )
    return facts


def _results(service: "MatchdayService") -> list[RecapFact]:
    return [
        RecapFact(
            fact_id=f"ft:{m.match_id}",
            match_id=m.match_id,
            text=f"Full time: {m.home.name} {h}-{a} {m.away.name}.",
        )
        for m in service.matches
        for h, a in [m.result.score_at(m.result.full_time_ms)]
    ]


def facts_text(facts: list[RecapFact]) -> str:
    """The facts as the recap writer and the fact-checker read them."""

    def lines(prefix: str) -> str:
        return "\n".join(f"- {f.fact_id}: {f.text}" for f in facts if f.fact_id.startswith(prefix))

    moments = "\n".join(
        f"- {f.fact_id}: {f.text}" for f in facts if not f.fact_id.startswith(("final:", "ft:"))
    )
    return (
        f"HOW IT ENDED:\n{lines('final:')}\n"
        f"THE GOALS THAT MOVED THE TABLE OR THE GOLDEN BOOT, IN TIME ORDER:\n{moments}\n"
        f"FINAL SCORES:\n{lines('ft:')}"
    )


def code_recap(facts: list[RecapFact]) -> tuple[str, str, list[RecapBeat]]:
    """The recap when no agent's draft passed: the facts themselves, in order."""
    by_id = {f.fact_id: f for f in facts}
    headline = by_id["final:champions"].text.split(" are champions")[0] + " are champions"
    standfirst = " ".join(
        by_id[i].text.split(". ")[0].rstrip(".") + "."
        for i in ("final:champions", "final:relegated", "final:golden_boot")
    )
    beats = [
        RecapBeat(
            minute=f.minute or 0,
            match_id=f.match_id,
            text=f.text.split(": ", 1)[-1],
            fact_ids=[f.fact_id],
        )
        for f in facts
        if f.minute is not None
    ]
    return headline, standfirst, beats


class RecapDesk:
    """Serves the recap: pending while matches are playing, then written once and kept."""

    def __init__(
        self,
        service: "MatchdayService",
        writer: "RecapWriter | None" = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.service = service
        self.writer = writer
        self.cache_dir = cache_dir
        self.loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self._ready: Recap | None = None
        self._writing = False

    def names(self) -> frozenset[str]:
        """Every club's name and every player's surname, for the recap's checker: a player is
        named by surname in the facts, so "Amadou Ambrose" counts where the facts say Ambrose."""
        clubs = {c.name for c in self.service.clubs.values()}
        players = {p.name.split(" ", 1)[-1] for p, _ in self.service.fantasy.players.values()}
        return frozenset(clubs | players)

    def start(self) -> None:
        """Remember the app's event loop, where the writer runs (call from the lifespan)."""
        self.loop = asyncio.get_running_loop()

    def snapshot(self, clock_ms: int) -> Recap:
        if clock_ms < self.service.over_ms:
            return Recap(status="pending")
        with self._lock:
            if self._ready:
                return self._ready
            facts = day_facts(self.service)
            cached = self._cached()
            if cached is not None:
                self._ready = self._recap(facts, cached)
            elif self.writer is None or self.loop is None:
                self._ready = self._recap(facts, None)
            elif not self._writing:
                self._writing = True
                asyncio.run_coroutine_threadsafe(self._write(facts), self.loop)
            return self._ready or Recap(status="writing", facts=facts, **self._outcome_refs())

    async def _write(self, facts: list[RecapFact]) -> None:
        assert self.writer
        start = time.perf_counter()
        with run_span("recap writer", matchday=self.service.fingerprint) as span:
            try:
                draft, tokens, checks = await self.writer.write(facts, self.names())
            except Exception as error:
                log.exception("the recap writer failed; the code writes the recap")
                draft, tokens, checks = (
                    None,
                    0,
                    [f"The recap writer failed ({failure_reason(error)})"],
                )
            for check in checks:
                span.add_event("sent back", {"reason": check})
            ended(
                span,
                "ready" if draft else "failed_checks",
                None if draft else "no draft passed: the code writes the recap",
                drafts=len(checks) + (1 if draft else 0),
                tokens=tokens,
            )
        run = {
            "draft": draft.model_dump() if draft else None,
            "checks": checks,
            "tokens": tokens,
            "seconds": round(time.perf_counter() - start, 2),
            "generated_at": datetime.now(UTC).isoformat(),
        }
        self._remember(run)
        with self._lock:
            self._ready = self._recap(facts, run)
            self._writing = False

    def _recap(self, facts: list[RecapFact], run: dict[str, Any] | None) -> Recap:
        draft = run and run["draft"]
        if draft:
            headline, standfirst = draft["headline"], draft["standfirst"]
            by_id = {f.fact_id: f for f in facts}
            beats = [
                RecapBeat(
                    minute=b["minute"],
                    match_id=next(
                        (by_id[i].match_id for i in b["fact_ids"] if by_id[i].match_id), None
                    ),
                    text=b["text"],
                    fact_ids=b["fact_ids"],
                )
                for b in draft["beats"]
            ]
        else:
            headline, standfirst, beats = code_recap(facts)
        return Recap(
            status="ready",
            written_by="agents" if draft else "code",
            headline=headline,
            standfirst=standfirst,
            beats=beats,
            facts=facts,
            checks=list(run["checks"]) if run else [],
            **self._outcome_refs(),
        )

    def _outcome_refs(self) -> dict[str, Any]:
        table = self.service.table_at(self.service.over_ms)
        leaders = [s for s in table.golden_boot.rows if s.position == 1]
        return {
            "champions": table.rows[0].club,
            "top_four": [r.club for r in table.rows if r.position <= 4],
            "relegated": [r.club for r in table.rows if r.zone == "relegation"],
            "golden_boot": leaders[0] if leaders else None,
        }

    # --- Cache: one recap per matchday, prompt version, and models ---------------------------

    def _key(self) -> dict[str, str]:
        assert self.writer
        return {
            "version": self.writer.version,
            "model": self.writer.model,
            "matchday": self.service.fingerprint,
        }

    def _cached(self) -> dict[str, Any] | None:
        if self.writer is None or self.cache_dir is None:
            return None
        try:
            data = json.loads((self.cache_dir / CACHE_FILE).read_text())
        except (OSError, ValueError):
            return None
        if all(data.get(k) == v for k, v in self._key().items()):
            run: dict[str, Any] = data["run"]
            return run
        return None

    def _remember(self, run: dict[str, Any]) -> None:
        if self.cache_dir is None:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {**self._key(), "run": run}
        (self.cache_dir / CACHE_FILE).write_text(json.dumps(payload, indent=1))


def _names(items: Any) -> str:
    names = list(items)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}"


def _count(n: int, noun: str) -> str:
    return f"{'a' if n == 1 else n} {noun}{'' if n == 1 else 's'}"
