"""What the agent team is told about a moment: the brief.

A brief is everything the team may use to write a graphic, and nothing else: the moment, the
events behind it (citable by id), the figures code computed from those events (a share of passes,
a distance covered, a team's xG), the plays leading up to it, the score and stats, and each
club's style as background. The checker holds every draft to it: an event id, a number, or a
player's name that isn't in the brief is a problem.
"""

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.generator.tactics import STYLE_NAMES
from app.generator.world import Club
from app.live.copy import CopyContext, distance_to_goal
from app.models import Claim, MatchEvent
from app.state.aggregator import team_stats
from app.state.xt import to_frame

LEAD_UP_EVENTS = 8
ON_BALL = ("pass", "shot", "goal", "save", "tackle", "foul", "offside", "card")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class EventFact:
    event_id: str
    text: str
    players: tuple[str, ...]  # surnames involved

    @property
    def numbers(self) -> frozenset[float]:
        return numbers_in(self.text)


@dataclass(frozen=True)
class Figure:
    """A number code computed from events: the moment's own claims (cues.py, aggregator.py)."""

    text: str
    event_ids: frozenset[str]

    @property
    def numbers(self) -> frozenset[float]:
        return numbers_in(self.text)


@dataclass(frozen=True)
class MomentBrief:
    match_id: str
    moment_id: str
    kind: str
    label: str
    clock_ms: int
    situation: str
    evidence: tuple[EventFact, ...]
    lead_up: tuple[EventFact, ...]
    stats: str
    background: str
    players: dict[str, str]  # player_id -> "Surname (CLUB #n)", everyone in the match
    figures: tuple[Figure, ...] = ()
    queue: str = ""  # the live queue and the producer's recent decisions (for the Producer)

    @property
    def citable(self) -> dict[str, EventFact]:
        return {f.event_id: f for f in (*self.evidence, *self.lead_up)}

    def supported(self, event_ids: Iterable[str]) -> frozenset[float]:
        """Numbers code computed from these events: the figures they're behind, and the moment's
        label (its number comes from the events behind the moment)."""
        ids = set(event_ids)
        found: set[float] = set()
        if ids & {f.event_id for f in self.evidence}:
            found |= numbers_in(self.label)
        for figure in self.figures:
            if ids & figure.event_ids:
                found |= figure.numbers
        return frozenset(found)

    @property
    def surnames(self) -> frozenset[str]:
        return frozenset(name.split(" (")[0] for name in self.players.values())

    def text(self) -> str:
        """The brief as the agents read it."""

        def facts(items: tuple[EventFact, ...]) -> str:
            return "\n".join(f"- {f.event_id}: {f.text}" for f in items) or "- (none)"

        figures = "".join(f"- {f.text}\n" for f in self.figures)
        if figures:
            figures = (
                "FIGURES (computed from the events behind it; a claim citing those events may "
                f"use them):\n{figures}"
            )
        return (
            f"MOMENT: {self.label} ({self.kind})\n"
            f"SITUATION: {self.situation}\n"
            f"EVENTS BEHIND IT (citable):\n{facts(self.evidence)}\n"
            f"{figures}"
            f"LEAD-UP (citable):\n{facts(self.lead_up)}\n"
            f"STATS SO FAR: {self.stats}\n"
            f"BACKGROUND (not citable, never a claim): {self.background}"
        )

    @property
    def numbers(self) -> frozenset[float]:
        """Every number the team may use: anything in the brief, plus each event's minute."""
        found = set(numbers_in(self.text()))
        minute = self.clock_ms // 60_000
        found.update({minute, minute + 1})
        return frozenset(found)


def numbers_in(text: str) -> frozenset[float]:
    return frozenset(float(n.replace(",", ".")) for n in NUMBER.findall(text))


def build_brief(
    moment_id: str,
    kind: str,
    label: str,
    clock_ms: int,
    evidence_ids: list[str],
    events: list[MatchEvent],
    ctx: CopyContext,
    home: Club,
    away: Club,
    figures: Sequence[Claim] = (),
) -> MomentBrief:
    """Everything the team may use for one moment, as of `clock_ms`. `figures` are the moment's
    scripted claims: numbers code computed from its events."""
    players = {
        p.player_id: f"{p.name.split(' ', 1)[-1]} ({club.short} #{p.number})"
        for club in (home, away)
        for p in club.squad
    }
    evidence = tuple(_fact(ctx.events[i], ctx, players) for i in evidence_ids if i in ctx.events)
    cited = set(evidence_ids)
    lead_up = tuple(
        _fact(e, ctx, players)
        for e in [
            e
            for e in events
            if e.match_clock_ms <= clock_ms and e.type in ON_BALL and e.event_id not in cited
        ][-LEAD_UP_EVENTS:]
    )
    home_goals, away_goals = ctx.score_at(clock_ms)
    minute = clock_ms // 60_000 + 1
    situation = (
        f"{home.name} ({home.short}, home) {home_goals}-{away_goals} {away.name} "
        f"({away.short}, away), {minute}' ({'1st' if minute <= 45 else '2nd'} half)"
    )
    stats = "; ".join(
        _stats_line(club, events, ctx, home.club_id, clock_ms) for club in (home, away)
    )
    background = " ".join(_tactics_line(club) for club in (home, away))
    return MomentBrief(
        match_id=events[0].match_id if events else "",
        moment_id=moment_id,
        kind=kind,
        label=label,
        clock_ms=clock_ms,
        situation=situation,
        evidence=evidence,
        lead_up=lead_up,
        stats=stats,
        background=background,
        players=players,
        figures=tuple(Figure(c.text, frozenset(c.evidence_event_ids)) for c in figures),
    )


def _stats_line(
    club: Club, events: list[MatchEvent], ctx: CopyContext, home_id: str, clock_ms: int
) -> str:
    s = team_stats(events, ctx.impacts, club.club_id, home_id, clock_ms)
    return (
        f"{club.short} {s.shots} shots ({s.xg:.2f} xG, {s.shots_on_target} on target), "
        f"{round(s.possession_pct)}% possession, {round(s.field_tilt_pct)}% field tilt, "
        f"{s.offsides} offsides"
    )


def _tactics_line(club: Club) -> str:
    # Only the style: the details live in the knowledge base, for the Explainer to look up.
    return f"{club.name} play a {STYLE_NAMES[club.tactics.style]} style."


def _zone(e: MatchEvent, home: bool) -> str:
    assert e.location
    x, y = to_frame((e.location.x, e.location.y), home)
    third = "own third" if x < 33.3 else "midfield" if x < 66.7 else "final third"
    lane = "left" if y > 66.7 else "right" if y < 33.3 else "central"
    return f"{third}, {lane}"


def _fact(e: MatchEvent, ctx: CopyContext, players: dict[str, str]) -> EventFact:
    who = players.get(e.player_id or "", "?")
    target = players.get(e.target_player_id or "", "?")
    home = e.team_id == ctx.home_id
    minute = f"{e.minute + 1}'"
    a = e.attributes
    impact = ctx.impacts.get(e.event_id)
    zone = f" ({_zone(e, home)})" if e.location else ""
    score_after = ctx.score_at(e.match_clock_ms)
    text = {
        "pass": lambda: (
            f"{who} {'completed' if e.outcome == 'success' else 'misplaced'} a "
            f"{round(a.pass_distance_m or 0)} m pass to {target}{zone}"
            + (f", +{impact.threat:.3f} xT" if impact and impact.threat > 0 else "")
        ),
        "shot": lambda: (
            f"{who} shot from {distance_to_goal(e, home)} m{zone}, "
            f"{impact.threat if impact else 0:.2f} xG, {(e.outcome or '').replace('_', ' ')}"
        ),
        "goal": lambda: f"GOAL by {who}, making it {'-'.join(map(str, score_after))}",
        "save": lambda: f"{who} made a save",
        "tackle": lambda: f"{who} won the ball{zone}",
        "foul": lambda: f"{who} committed a foul{zone}",
        "card": lambda: f"{a.card_color} card for {who}",
        "offside": lambda: f"{who} was flagged offside{zone}",
        "substitution": lambda: (
            f"{target} replaced {who}, who had covered "
            f"{(a.distance_covered_m or 0) / 1000:.1f} km"
        ),
        "sprint": lambda: (
            f"{who} sprinted {round(a.sprint_distance_m or 0)} m, top speed "
            f"{a.top_speed_kmh or 0:.1f} km/h"
        ),
    }.get(e.type, lambda: f"{e.type.replace('_', ' ')} by {who}{zone}")()
    involved = tuple(
        players[p].split(" (")[0] for p in (e.player_id, e.target_player_id) if p in players
    )
    return EventFact(e.event_id, f"{minute} {text}", involved)


def is_close(value: float, allowed: frozenset[float]) -> bool:
    """A number matches the brief if it equals one of its numbers, or rounds from one."""
    for b in allowed:
        if math.isclose(value, b, abs_tol=0.011):
            return True
        if any(math.isclose(value, round(b, digits), abs_tol=1e-9) for digits in (0, 1, 2)):
            return True
    return False
