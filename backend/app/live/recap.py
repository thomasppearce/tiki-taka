"""How the matchday unfolded: the facts, written by code, and the recap built on them.

Any matchday; the demo's is the season's last. Once the last match of the day ends, the recap
writer (app/agents/recap.py) tells the day's story from these facts, and every beat cites them by
id:
- where the day left the table: the top, the top four, the bottom three, the Golden Boot race,
  and the last goal to change each (`table:top`, `table:top_four`, `table:bottom`,
  `table:golden_boot`, `table:deciders`). On the season's last matchday these are how it ended:
  the champions, the relegated, the Golden Boot;
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
from typing import TYPE_CHECKING, Any, cast

from app.agents.channel_brief import match_brief
from app.agents.drill import failure_reason
from app.agents.recap import RECAP_VERSION
from app.agents.tracing import ended, run_span
from app.generator.season import LEAGUE_GAMES
from app.models.matchday import ClubRef
from app.models.proposals import Claim
from app.models.recap import MatchRecap, Recap, RecapBeat, RecapFact
from app.models.table import LeagueTable
from app.state.table import _ordinal

if TYPE_CHECKING:
    from app.agents.channel_brief import MatchBrief
    from app.agents.channel_team import ChannelTeam
    from app.agents.recap import RecapWriter
    from app.live.service import MatchdayService

log = logging.getLogger(__name__)

CACHE_FILE = "recap.json"


def day_facts(service: "MatchdayService") -> list[RecapFact]:
    """Everything the recap may say, as of the final whistle, each with an id to cite."""
    table = service.table_at(service.over_ms)
    return [*_outcomes(service, table), *_moments(service, table), *_results(service)]


def season_over(table: LeagueTable) -> bool:
    """Whether this was the season's last matchday: every club has played all its games."""
    return all(r.played >= LEAGUE_GAMES for r in table.rows)


def _outcomes(service: "MatchdayService", table: LeagueTable) -> list[RecapFact]:
    """Where the round left the table. On the season's last matchday that is how it ended: the
    champions, the top four, the relegated, the Golden Boot."""
    rows = table.rows
    last = season_over(table)
    n = rows[0].played
    first, second = rows[0], rows[1]
    gap = first.points - second.points
    if last:
        margin = "on goal difference" if gap == 0 else f"by {_count(gap, 'point')}"
        top = (
            f"{first.club.name} are champions {margin}, on {first.points} points; they started "
            f"the day {_ordinal(first.start_position)}. {second.club.name} finish 2nd on "
            f"{second.points} points, having started {_ordinal(second.start_position)}."
        )
    else:
        lead = "on goal difference" if gap == 0 else f"by {_count(gap, 'point')}"
        top = (
            f"{first.club.name} top the table after matchday {n}, {lead}, on {first.points} "
            f"points; they started the day {_ordinal(first.start_position)}. "
            f"{second.club.name} are 2nd on {second.points} points."
        )
    four = [r for r in rows if r.position <= 4]
    climbed = [r for r in four if r.start_position > 4]
    dropped = [r for r in rows if r.position > 4 and r.start_position <= 4]
    top_four = (
        f"The top four{'' if last else f' after matchday {n}'}: "
        f"{_names(r.club.name for r in four)}."
        + "".join(f" {r.club.name} climb in from {_ordinal(r.start_position)}." for r in climbed)
        + "".join(
            f" {r.club.name} drop out, from {_ordinal(r.start_position)} to {_ordinal(r.position)}."
            for r in dropped
        )
    )
    down = [r for r in rows if r.zone == "relegation"]
    dipped = {c.club_id for s in table.swings for c in s.changes if c.to_zone == "relegation"}
    survived = [r for r in rows if r.club.club_id in dipped and r.zone != "relegation"]
    bottom = (
        f"Relegated: {_names(r.club.name for r in down)}."
        if last
        else f"The bottom three after matchday {n}: {_names(r.club.name for r in down)}."
    ) + "".join(
        f" {r.club.name} {'stay up' if last else 'finish the day out of the bottom three'} in "
        f"{_ordinal(r.position)}, after time in the relegation zone today."
        for r in survived
    )
    boot = table.golden_boot.rows
    leaders = [s for s in boot if s.position == 1]
    chasers = [s for s in boot if s.position > 1][:2]
    golden = (
        ("The Golden Boot: " if last else "Leading the Golden Boot race: ")
        + _names(f"{s.name} ({s.club.name})" for s in leaders)
        + f", {leaders[0].goals} league goals"
        + (f", {leaders[0].today} of them today" if len(leaders) == 1 and leaders[0].today else "")
        + ". Next: "
        + "; ".join(f"{s.name} {s.goals}" for s in chasers)
        + "."
    )
    return [
        RecapFact(fact_id="table:top", text=top),
        RecapFact(fact_id="table:top_four", text=top_four),
        RecapFact(fact_id="table:bottom", text=bottom),
        RecapFact(fact_id="table:golden_boot", text=golden),
        RecapFact(fact_id="table:deciders", text=_deciders(service, table, last)),
    ]


def _deciders(service: "MatchdayService", table: LeagueTable, last: bool) -> str:
    """The last goal that changed each race today: so "one goal settled two races" is a fact
    the recap can cite, not a reading of its own."""
    races = (
        ("the title", "the top four", "the drop", "the Golden Boot")
        if last
        else ("top spot", "the top four", "the bottom three", "the Golden Boot lead")
    )

    def race(change: Any) -> str:
        zones = {change.from_zone, change.to_zone}
        if "champions" in zones:
            return races[0]
        if "relegation" in zones:
            return races[2]
        return races[1]

    latest: dict[str, tuple[int, str, str]] = {}
    for swing in table.swings:
        for change in swing.changes:
            latest[race(change)] = (swing.match_clock_ms, swing.match_id, swing.event_id)
    for boot in table.golden_boot.swings:
        latest[races[3]] = (boot.match_clock_ms, boot.match_id, boot.event_id)

    def scorer(match_id: str, event_id: str) -> str:
        event = next(e for e in service.by_id[match_id].result.events if e.event_id == event_id)
        player, club = service.fantasy.players[event.player_id or ""]
        return f"{player.name} for {club.name}"

    parts = []
    for name in races:
        if name in latest:
            clock, match_id, event_id = latest[name]
            parts.append(f"{name} at {clock // 60_000 + 1}' ({scorer(match_id, event_id)})")
        else:
            parts.append(f"{name}: no goal changed it today")
    return (
        "The last goal to change each race today: "
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
        f"WHERE THE DAY LEFT THE TABLE:\n{lines('table:')}\n"
        f"THE GOALS THAT MOVED THE TABLE OR THE GOLDEN BOOT, IN TIME ORDER:\n{moments}\n"
        f"FINAL SCORES:\n{lines('ft:')}"
    )


def code_recap(facts: list[RecapFact]) -> tuple[str, str, list[RecapBeat]]:
    """The recap when no agent's draft passed: the facts themselves, in order."""
    by_id = {f.fact_id: f for f in facts}
    top = by_id["table:top"].text
    if " are champions" in top:
        headline = top.split(" are champions")[0] + " are champions"
    else:
        headline = top.split(", ")[0]  # "Halvern Town top the table after matchday 30"
    standfirst = " ".join(
        by_id[i].text.split(". ")[0].rstrip(".") + "."
        for i in ("table:top", "table:bottom", "table:golden_boot")
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


def code_match_recap(brief: "MatchBrief", home: str, away: str) -> tuple[str, str, list[Claim]]:
    """A match's recap when no Watcher draft passed: the result and its goals, from code."""
    h, a = brief.scores[-1]
    if h == a:
        headline = f"{home} and {away} draw {h}-{a}"
    else:
        winner, loser = (home, away) if h > a else (away, home)
        headline = f"{winner} beat {loser} {max(h, a)}-{min(h, a)}"
    story = ("Goals: " + "; ".join(brief.goals) + ".") if brief.goals else "No goals."
    claims = [
        Claim(text=f.text, evidence_event_ids=[f.event_id])
        for f in brief.events
        if " GOAL by " in f" {f.text}"
    ]
    return headline, story, claims


class RecapDesk:
    """Serves the recaps: the matchday's once its last match ends, and each match's at its final
    whistle. Each is written once (the agents, or code), cached, and kept."""

    def __init__(
        self,
        service: "MatchdayService",
        writer: "RecapWriter | None" = None,
        crew: "ChannelTeam | None" = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.service = service
        self.writer = writer  # the matchday's recap
        self.crew = crew  # each match's Watcher writes its match's recap
        self.cache_dir = cache_dir
        self.loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self._ready: dict[str, Any] = {}  # "day" or a match id -> Recap | MatchRecap
        self._writing: set[str] = set()
        self._runs: dict[str, Any] | None = None

    def names(self) -> frozenset[str]:
        """Every club's name and every player's surname, for the recap's checker: a player is
        named by surname in the facts, so "Amadou Ambrose" counts where the facts say Ambrose."""
        clubs = {c.name for c in self.service.clubs.values()}
        players = {p.name.split(" ", 1)[-1] for p, _ in self.service.fantasy.players.values()}
        return frozenset(clubs | players)

    def start(self) -> None:
        """Remember the app's event loop, where the writers run (call from the lifespan)."""
        self.loop = asyncio.get_running_loop()

    # --- The matchday ------------------------------------------------------------------------

    def snapshot(self, clock_ms: int, ended: bool = False) -> Recap:
        """The matchday's recap; `ended` asks for it whatever the clock says (the /recap page)."""
        if not ended and clock_ms < self.service.over_ms:
            return Recap(status="pending")
        with self._lock:
            ready = self._ready.get("day")
            if ready:
                return cast(Recap, ready)
            facts = day_facts(self.service)
            cached = self._cached("day")
            if cached is not None or self.writer is None or self.loop is None:
                recap = self._day(facts, cached)
                self._ready["day"] = recap
                return recap
            if "day" not in self._writing:
                self._writing.add("day")
                asyncio.run_coroutine_threadsafe(self._write_day(facts), self.loop)
            return Recap(status="writing", facts=facts, **self._outcome_refs())

    async def _write_day(self, facts: list[RecapFact]) -> None:
        assert self.writer
        start = time.perf_counter()
        with run_span("recap writer", matchday=self.service.fingerprint) as span:
            try:
                last = season_over(self.service.table_at(self.service.over_ms))
                draft, tokens, checks = await self.writer.write(facts, self.names(), last)
            except Exception as error:
                log.exception("the recap writer failed; the code writes the recap")
                draft, tokens, checks = (
                    None,
                    0,
                    [f"The recap writer failed ({failure_reason(error)})"],
                )
            _ended(span, draft is not None, checks, tokens)
        run = _run(draft, checks, tokens, start)
        self._remember("day", run)
        with self._lock:
            self._ready["day"] = self._day(facts, run)
            self._writing.discard("day")

    def _day(self, facts: list[RecapFact], run: dict[str, Any] | None) -> Recap:
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
            "matchday": table.rows[0].played,
            "season_over": season_over(table),
            "top": table.rows[0].club,
            "top_four": [r.club for r in table.rows if r.position <= 4],
            "bottom_three": [r.club for r in table.rows if r.zone == "relegation"],
            "golden_boot": leaders[0] if leaders else None,
        }

    # --- Each match ----------------------------------------------------------------------------

    def match(self, match_id: str, clock_ms: int, ended: bool = False) -> MatchRecap:
        """A match's recap, once it has ended (or whatever the clock says, if `ended`)."""
        m = self.service.by_id[match_id]
        if not ended and clock_ms < m.result.full_time_ms:
            return MatchRecap(status="pending", **self._fixture(match_id))
        with self._lock:
            ready = self._ready.get(match_id)
            if ready:
                return cast(MatchRecap, ready)
            brief = match_brief(self.service, match_id, m.result.full_time_ms, None, full=True)
            cached = self._cached(match_id)
            if cached is not None or self.crew is None or self.loop is None:
                recap = self._match(match_id, brief, cached)
                self._ready[match_id] = recap
                return recap
            if match_id not in self._writing:
                self._writing.add(match_id)
                asyncio.run_coroutine_threadsafe(self._write_match(match_id, brief), self.loop)
            return MatchRecap(status="writing", **self._fixture(match_id))

    async def _write_match(self, match_id: str, brief: "MatchBrief") -> None:
        assert self.crew
        start = time.perf_counter()
        with run_span("match recap", match_id=match_id, matchday=self.service.fingerprint) as span:
            try:
                draft, tokens, checks = await self.crew.recap(brief)
            except Exception as error:
                log.exception("the Watcher's recap failed; the code writes it")
                draft, tokens, checks = None, 0, [f"The Watcher failed ({failure_reason(error)})"]
            _ended(span, draft is not None, checks, tokens)
        run = _run(draft, checks, tokens, start)
        self._remember(match_id, run)
        with self._lock:
            self._ready[match_id] = self._match(match_id, brief, run)
            self._writing.discard(match_id)

    def _match(self, match_id: str, brief: "MatchBrief", run: dict[str, Any] | None) -> MatchRecap:
        draft = run and run["draft"]
        if draft:
            headline, story = draft["headline"], draft["story"]
            claims = [Claim(**c) for c in draft["claims"]]
        else:
            m = self.service.by_id[match_id]
            headline, story, claims = code_match_recap(brief, m.home.name, m.away.name)
        return MatchRecap(
            status="ready",
            **self._fixture(match_id),
            written_by="agents" if draft else "code",
            headline=headline,
            story=story,
            claims=claims,
            checks=list(run["checks"]) if run else [],
        )

    def _fixture(self, match_id: str) -> dict[str, Any]:
        m = self.service.by_id[match_id]
        home, away = m.result.score_at(m.result.full_time_ms)
        return {
            "match_id": match_id,
            "home": _club_ref(m.home),
            "away": _club_ref(m.away),
            "score_home": home,
            "score_away": away,
        }

    # --- Cache: the matchday's recap and each match's, per prompt version and models ---------

    def _key(self) -> dict[str, str]:
        return {
            "version": RECAP_VERSION,
            "model": self.writer.model if self.writer else "",
            "matchday": self.service.fingerprint,
        }

    def _all_runs(self) -> dict[str, Any]:
        if self._runs is None:
            self._runs = {}
            if self.cache_dir is not None:
                try:
                    data = json.loads((self.cache_dir / CACHE_FILE).read_text())
                    if all(data.get(k) == v for k, v in self._key().items()):
                        self._runs = data["runs"]
                except (OSError, ValueError, KeyError):
                    pass
        return self._runs

    def _cached(self, key: str) -> dict[str, Any] | None:
        if self.writer is None and self.crew is None:
            return None  # agents off: the code writes it, nothing to replay
        run: dict[str, Any] | None = self._all_runs().get(key)
        return run

    def _remember(self, key: str, run: dict[str, Any]) -> None:
        runs = self._all_runs()
        runs[key] = run
        if self.cache_dir is None:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {**self._key(), "runs": runs}
        (self.cache_dir / CACHE_FILE).write_text(json.dumps(payload, indent=1))


def _run(draft: Any, checks: list[str], tokens: int, start: float) -> dict[str, Any]:
    return {
        "draft": draft.model_dump() if draft else None,
        "checks": checks,
        "tokens": tokens,
        "seconds": round(time.perf_counter() - start, 2),
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _ended(span: Any, passed: bool, checks: list[str], tokens: int) -> None:
    for check in checks:
        span.add_event("sent back", {"reason": check})
    ended(
        span,
        "ready" if passed else "failed_checks",
        None if passed else "no draft passed: the code writes the recap",
        drafts=len(checks) + (1 if passed else 0),
        tokens=tokens,
    )


def _names(items: Any) -> str:
    names = list(items)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}"


def _count(n: int, noun: str) -> str:
    return f"{'a' if n == 1 else n} {noun}{'' if n == 1 else 's'}"


def _club_ref(club: Any) -> ClubRef:
    return ClubRef(club_id=club.club_id, name=club.name, short=club.short, color=club.color)
