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
from app.state.table import _ordinal
from app.state.xt import to_frame

LEAD_UP_EVENTS = 8
ON_BALL = ("pass", "shot", "goal", "save", "tackle", "foul", "offside", "card")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class EventFact:
    event_id: str
    text: str
    players: tuple[str, ...]  # surnames involved
    clock_ms: int = 0

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
    stories: tuple[str, ...] = ()  # the players' stories (the Golden Boot race...), by code

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

        latest = max(
            (*self.evidence, *self.lead_up), key=lambda f: (f.clock_ms, f.event_id), default=None
        )

        def facts(items: tuple[EventFact, ...]) -> str:
            lines = [
                f"- {f.event_id}: {f.text}" + (" (the latest event)" if f is latest else "")
                for f in sorted(items, key=lambda f: (f.clock_ms, f.event_id))
            ]
            return "\n".join(lines) or "- (none)"

        figures = "".join(f"- {f.text}\n" for f in self.figures)
        if figures:
            figures = (
                "FIGURES (computed from the events behind it; a claim citing those events may "
                f"use them):\n{figures}"
            )
        return (
            f"MOMENT: {self.label} ({self.kind})\n"
            f"SITUATION: {self.situation}\n"
            f"EVENTS BEHIND IT (citable, in time order):\n{facts(self.evidence)}\n"
            f"{figures}"
            "LEAD-UP (citable, in time order; these may come before or between the events "
            f"above):\n{facts(self.lead_up)}\n"
            f"STATS SO FAR:\n{self.stats}\n"
            + (
                "PLAYER STORIES (true, and may be quoted word for word when the moment is about "
                f"that player; never listed as a claim): {' | '.join(self.stories)}\n"
                if self.stories
                else ""
            )
            + "BACKGROUND (how each club usually plays: it may describe a club, but it is not "
            f"evidence of what happened in this moment): {self.background}"
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
    stories: Sequence[str] = (),
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
    half_time = next((e.match_clock_ms for e in events if e.type == "half_end"), None)
    first_half = half_time is None or clock_ms <= half_time
    stoppage = minute > (45 if first_half else 90)
    if home_goals == away_goals:
        standing = f"level at {home_goals}-{away_goals}"
    else:
        leader = home if home_goals > away_goals else away
        standing = f"{leader.name} lead {max(home_goals, away_goals)}-{min(home_goals, away_goals)}"
    situation = (
        f"{home.name} ({home.short}, home) {home_goals}-{away_goals} {away.name} "
        f"({away.short}, away): {standing}. {minute}', "
        f"{'1st' if first_half else '2nd'} half{', stoppage time' if stoppage else ''}"
    )
    stats = _stats(home, away, events, ctx, clock_ms)
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
        stories=tuple(stories),
    )


def _stats(home: Club, away: Club, events: list[MatchEvent], ctx: CopyContext, t: int) -> str:
    """Each club's numbers on its own line, by name, then which club is ahead on each, so no
    one has to work out from two abbreviations which side has more of the ball."""
    s = {
        c.club_id: team_stats(events, ctx.impacts, c.club_id, home.club_id, t) for c in (home, away)
    }
    lines = [
        f"- {c.name} ({c.short}): {_count(s[c.club_id].shots, 'shot')} "
        f"({s[c.club_id].xg:.2f} xG, {s[c.club_id].shots_on_target} on target), "
        f"{round(s[c.club_id].possession_pct)}% possession, "
        f"{round(s[c.club_id].field_tilt_pct)}% field tilt, "
        f"{_count(s[c.club_id].offsides, 'offside')}"
        for c in (home, away)
    ]
    h, a = s[home.club_id], s[away.club_id]

    def ahead(what: str, hv: float, av: float, shown: str) -> str:
        if round(hv, 2) == round(av, 2):
            return f"{what}: even"
        return f"{what}: {(home if hv > av else away).name} ({shown})"

    lines.append(
        "- Ahead: "
        + "; ".join(
            (
                ahead(
                    "more of the ball",
                    h.possession_pct,
                    a.possession_pct,
                    f"{round(max(h.possession_pct, a.possession_pct))}%",
                ),
                ahead(
                    "more of the territory",
                    h.field_tilt_pct,
                    a.field_tilt_pct,
                    f"{round(max(h.field_tilt_pct, a.field_tilt_pct))}% field tilt",
                ),
                ahead(
                    "more shots",
                    h.shots,
                    a.shots,
                    f"{max(h.shots, a.shots)} to {min(h.shots, a.shots)}",
                ),
                ahead(
                    "better chances",
                    h.xg,
                    a.xg,
                    f"{max(h.xg, a.xg):.2f} xG to {min(h.xg, a.xg):.2f}",
                ),
            )
        )
    )
    return "\n".join(lines)


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def _so_far(e: MatchEvent, ctx: CopyContext, noun: str) -> str:
    """'(Westmere Athletic's 1st offside of the match)': how many of these the club has had,
    counting this one, so nobody writes "again" about the first."""
    n = sum(
        1
        for x in ctx.events.values()
        if x.type == e.type and x.team_id == e.team_id and x.match_clock_ms <= e.match_clock_ms
    )
    return f" ({ctx.club(e.team_id).name}'s {_ordinal(n)} {noun} of the match)"


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
            f"{who} played a {round(a.pass_distance_m or 0)} m pass to {target}{zone}, "
            f"who was caught offside"
            if e.event_id in ctx.offside_passes
            else (
                f"{who} completed a {round(a.pass_distance_m or 0)} m pass to {target}{zone}"
                + (f", +{impact.threat:.3f} xT" if impact and impact.threat > 0 else "")
                if e.outcome == "success"
                else f"{who} misplaced a {round(a.pass_distance_m or 0)} m pass meant for "
                f"{target}{zone}: it did not reach him"
            )
        ),
        "shot": lambda: (
            f"{who} shot from {distance_to_goal(e, home)} m{zone}, "
            f"{impact.threat if impact else 0:.2f} xG, {(e.outcome or '').replace('_', ' ')}"
        ),
        "goal": lambda: f"GOAL by {who}, making it {'-'.join(map(str, score_after))}",
        "save": lambda: f"{who} made a save",
        "tackle": lambda: f"{who} won the ball{zone}",
        "foul": lambda: f"{who} committed a foul{zone}",
        "card": lambda: f"{a.card_color} card for {who}" + _so_far(e, ctx, "card"),
        "offside": lambda: f"{who} was flagged offside{zone}" + _so_far(e, ctx, "offside"),
        "substitution": lambda: (
            f"{target} replaced {who}, who had covered "
            f"{(a.distance_covered_m or 0) / 1000:.1f} km" + _so_far(e, ctx, "substitution")
        ),
        "sprint": lambda: (
            f"{who} sprinted {round(a.sprint_distance_m or 0)} m, top speed "
            f"{a.top_speed_kmh or 0:.1f} km/h"
        ),
    }.get(e.type, lambda: f"{e.type.replace('_', ' ')} by {who}{zone}")()
    involved = tuple(
        players[p].split(" (")[0] for p in (e.player_id, e.target_player_id) if p in players
    )
    return EventFact(e.event_id, f"{minute} {text}", involved, e.match_clock_ms)


def is_close(value: float, allowed: frozenset[float]) -> bool:
    """A number matches the brief if it equals one of its numbers, or rounds from one."""
    for b in allowed:
        if math.isclose(value, b, abs_tol=0.011):
            return True
        if any(math.isclose(value, round(b, digits), abs_tol=1e-9) for digits in (0, 1, 2)):
            return True
    return False
