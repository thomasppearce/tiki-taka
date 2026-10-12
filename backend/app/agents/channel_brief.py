"""What the channel's agents are told about a match: the situation, what's at stake (code-written
from the live table), the day's table moves in this match, the citable events, and the Watcher's
latest story. As with graphics, the checker holds every answer to its brief."""

from bisect import bisect_right
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.agents.brief import EventFact, _fact, numbers_in

if TYPE_CHECKING:
    from app.generator.matchday import ScheduledMatch
    from app.live.service import MatchdayService
    from app.models.events import MatchEvent

BIG_CHANCE_XG = 0.1
RECENT_MS = 5 * 60_000
MAX_FACTS = 14
ZONE_NAMES = {
    "champions": "top (the champions' place)",
    "continental": "in the continental cup places",
    "relegation": "in the relegation zone",
}


@dataclass(frozen=True)
class MatchBrief:
    match_id: str
    fixture: str
    situation: str
    standing: str
    pressure: str
    stakes: tuple[str, ...]
    moves: tuple[str, ...]
    events: tuple[EventFact, ...]
    story: str | None
    surnames: frozenset[str]  # every player in the match
    scores: tuple[tuple[int, int], ...]  # every scoreline so far (home, away), the last is now
    goals: tuple[str, ...] = ()  # each goal, its scoreline, and what it did (code-written)
    stories: tuple[str, ...] = ()  # the players' stories here (the Golden Boot race...), by code

    @property
    def citable(self) -> dict[str, EventFact]:
        return {f.event_id: f for f in self.events}

    @property
    def involved(self) -> frozenset[str]:
        return frozenset(name for f in self.events for name in f.players)

    def text(self, label: str = "", watcher: bool = False) -> str:
        """The brief as the model reads it. The Watcher's leaves out the table (it tells the
        story on the pitch; the Director and the code say what it means for the table) and its
        own last story (rewriting it, the model kept a score that had changed)."""
        table = not watcher
        lines = [f"{label}MATCH {self.match_id}: {self.situation}"]
        if table:
            lines.append(f"AS IT STANDS NOW: {self.standing}")
        lines.append(f"PRESSURE NOW: {self.pressure}")
        lines.append("GOALS SO FAR: " + (" | ".join(self.goals) or "none"))
        if self.stories:
            lines.append("PLAYER STORIES: " + " | ".join(self.stories))
        if table:
            lines.append(
                "AT STAKE, IF EITHER SIDE SCORES NEXT: "
                + (
                    " | ".join(self.stakes)
                    if self.stakes
                    else "the next goal changes nothing in the table"
                )
            )
        if table and self.moves:
            lines.append("TABLE MOVES FROM THIS MATCH TODAY: " + " | ".join(self.moves))
        lines.append("EVENTS (citable):")
        lines += [f"- {f.event_id}: {f.text}" for f in self.events] or ["- (none yet)"]
        if self.story and not watcher:
            lines.append(f"STORY SO FAR (the Watcher's): {self.story}")
        return "\n".join(lines)

    @property
    def numbers(self) -> frozenset[float]:
        return numbers_in(self.text())


def match_brief(service: "MatchdayService", match_id: str, t: int, story: str | None) -> MatchBrief:
    """Everything an agent may say about one match at match time `t`."""
    m = service.by_id[match_id]
    at = min(t, m.result.full_time_ms)
    ctx = service.desks[match_id].ctx
    impacts = service.impacts[match_id]
    players = {
        p.player_id: f"{p.name.split(' ', 1)[-1]} ({club.short} #{p.number})"
        for club in (m.home, m.away)
        for p in club.squad
    }
    clocks = [e.match_clock_ms for e in m.result.events]
    seen = m.result.events[: bisect_right(clocks, at)]
    worth = [
        e
        for e in seen
        if e.type in ("goal", "card")
        or (
            e.type == "shot"
            and (impacts[e.event_id].threat >= BIG_CHANCE_XG or at - e.match_clock_ms <= RECENT_MS)
        )
    ]
    facts = tuple(_fact(e, ctx, players) for e in worth[-MAX_FACTS:])
    home, away = m.result.score_at(at)
    scores = [(0, 0)]
    goals: list[str] = []
    led: set[str] = set()  # sides that have been in front at some point
    for e in seen:
        if e.type != "goal":
            continue
        h, a = scores[-1]
        scores.append((h + 1, a) if e.team_id == m.home.club_id else (h, a + 1))
        goals.append(_goal_line(e, scores[-2], scores[-1], m, players, led))
    minute = at // 60_000 + 1
    half = (
        "full time" if at >= m.result.full_time_ms else ("1st half" if minute <= 45 else "2nd half")
    )
    situation = (
        f"{m.home.name} ({m.home.short}, home) {home}-{away} {m.away.name} ({m.away.short}, away), "
        f"{minute}' ({half})"
    )
    signal = next((x for x in service.channel.signals(at) if x.match_id == match_id), None)
    pressure = (
        f"{m.home.name} {_pressing(signal.home.pressure)}; "
        f"{m.away.name} {_pressing(signal.away.pressure)}"
        if signal
        else "the match has ended"
    )
    table = service._table(at // 1000)
    stakes = tuple(
        f"if {service.club(s.scorer_club_id).name} score next: {s.summary}"
        for s in table.stakes
        if s.match_id == match_id
    )
    rows = {r.club.club_id: r for r in table.rows}

    def place(club_id: str) -> str:
        r = rows[club_id]
        zone = f", {ZONE_NAMES[r.zone]}" if r.zone else ""
        return f"{r.club.name} {_ordinal(r.position)} on {r.points} points{zone}"

    standing = f"{place(m.home.club_id)}; {place(m.away.club_id)}"
    moves = tuple(
        f"{x.match_clock_ms // 60_000 + 1}': {x.summary}"
        for x in table.swings
        if x.match_id == match_id
    )
    return MatchBrief(
        match_id=match_id,
        fixture=f"{m.home.name} v {m.away.name}",
        situation=situation,
        standing=standing,
        pressure=pressure,
        stakes=stakes,
        moves=moves,
        events=facts,
        story=story,
        surnames=frozenset(name.split(" (")[0] for name in players.values()),
        scores=tuple(scores),
        goals=tuple(goals),
        stories=tuple(service.stories(match_id, t)),
    )


def _goal_line(
    goal: "MatchEvent",
    before: tuple[int, int],
    after: tuple[int, int],
    m: "ScheduledMatch",
    players: dict[str, str],
    led: set[str],
) -> str:
    """One goal as the brief gives it: who, the score it made, and what it did, worked out by
    code so the model never has to (it got "ahead again" and who equalised wrong)."""
    home = goal.team_id == m.home.club_id
    side = m.home.name if home else m.away.name
    ours = (after[0], after[1]) if home else (after[1], after[0])
    ours_before = (before[0], before[1]) if home else (before[1], before[0])
    if ours[0] == ours[1]:
        what = f"equaliser for {side}"
    elif ours[0] < ours[1]:
        what = f"{side} pull one back"
    elif ours_before[0] > ours_before[1]:
        what = f"{side} extend their lead"
    elif before == (0, 0):
        what = f"the opener, {side} lead"
    elif side in led:
        what = f"{side} back in front"
    else:
        what = f"{side} lead for the first time"
    if ours[0] > ours[1]:
        led.add(side)
    scorer = players.get(goal.player_id or "", "?").split(" (")[0]
    return f"{goal.minute + 1}' {scorer} ({side}): {after[0]}-{after[1]}, {what}"


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _pressing(pressure: float) -> str:
    """Pressure in words: the agents weigh it but never quote a number to viewers."""
    if pressure >= 0.8:
        return "relentless"
    if pressure >= 0.5:
        return "pushing hard"
    if pressure >= 0.2:
        return "building"
    return "quiet"
