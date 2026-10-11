"""Fantasy points for the league's fictional players, as it stands, every point with receipts.

A signed-in fan can follow a fantasy XI on their own whip-around (app/live/lens.py). The scoring
is this project's own, simple and close to what fantasy players expect; nothing here is a bet or
a price. Every line of a player's score cites the events that earned it, like every graphic.
The rules are in RULES, which the picker also shows, so the page and the code can't disagree.
"""

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.generator.world import Club, Player
from app.models.channel import FantasyItem, FantasyPlayer
from app.models.events import MatchEvent

if TYPE_CHECKING:
    from app.generator.matchday import ScheduledMatch

GOAL = {"gk": 6, "def": 6, "mid": 5, "fwd": 4}
ASSIST = 3
CLEAN_SHEET = {"gk": 4, "def": 4, "mid": 1, "fwd": 0}
FULL_APPEARANCE_MS = 60 * 60_000
SAVES_PER_POINT = 3
CONCEDED_PER_POINT = 2  # goalkeepers and defenders lose a point for every two conceded
YELLOW, RED = -1, -3

RULES = [
    "Playing: 1 point, or 2 for 60 minutes or more.",
    "Goal: 6 for a goalkeeper or defender, 5 for a midfielder, 4 for a forward.",
    "Assist (the pass, corner, or free kick the scorer shot from): 3.",
    "Clean sheet, 60 minutes or more without conceding: 4 for a goalkeeper or defender, "
    "1 for a midfielder.",
    "Goalkeepers and defenders: -1 for every 2 goals conceded while on the pitch.",
    "Goalkeepers: 1 for every 3 saves.",
    "Yellow card -1, red card -3.",
]

# Restarts and passes that can set up a goal; anything else in between means no assist.
ASSIST_TYPES = ("pass", "corner", "free_kick", "throw_in")
OFF_THE_BALL = ("sprint", "pressure")
XI_SHAPE = {"gk": (1, 1), "def": (3, 5), "mid": (2, 5), "fwd": (1, 3)}
XI_SIZE = 11
PER_CLUB = 3


@dataclass
class _Spell:
    """A player's time on the pitch: from kickoff or coming on, until going off (if they did)."""

    on_ms: int
    off_ms: int | None = None
    on_event: str | None = None
    off_event: str | None = None


@dataclass
class _Match:
    """Everything fantasy needs from one match, indexed once."""

    match: "ScheduledMatch"
    spells: dict[str, _Spell]
    goals: list[tuple[MatchEvent, str | None]]  # each goal and its assist's event id
    assisters: dict[str, str] = field(default_factory=dict)  # assist event id -> player id
    clocks: list[int] = field(default_factory=list)


class FantasyScorer:
    """Scores any player at any moment of the final day."""

    def __init__(self, matches: Sequence["ScheduledMatch"]) -> None:
        self.players: dict[str, tuple[Player, Club]] = {}
        self.match_of: dict[str, _Match] = {}
        for m in matches:
            indexed = _index(m)
            for club in (m.home, m.away):
                for p in club.squad:
                    self.players[p.player_id] = (p, club)
                    self.match_of[p.player_id] = indexed

    def score(self, player_id: str, t: int) -> FantasyPlayer:
        player, club = self.players[player_id]
        m = self.match_of[player_id]
        at = min(t, m.match.result.full_time_ms)
        events = m.match.result.events[: bisect_right(m.clocks, at)]
        spell = m.spells.get(player_id)
        items: list[FantasyItem] = []
        on_pitch = False
        if spell and spell.on_ms <= at:
            off = spell.off_ms if spell.off_ms is not None and spell.off_ms <= at else None
            on_pitch = off is None
            played = (off if off is not None else at) - spell.on_ms
            items.append(
                FantasyItem(
                    label="Playing 60 minutes" if played >= FULL_APPEARANCE_MS else "Playing",
                    points=2 if played >= FULL_APPEARANCE_MS else 1,
                    event_ids=[spell.on_event] if spell.on_event else [],
                )
            )
            role = player.role
            for goal, assist in m.goals:
                if goal.match_clock_ms > at:
                    break
                if goal.player_id == player_id:
                    items.append(
                        FantasyItem(label="Goal", points=GOAL[role], event_ids=[goal.event_id])
                    )
                if assist and m.assisters.get(assist) == player_id:
                    items.append(
                        FantasyItem(
                            label="Assist", points=ASSIST, event_ids=[assist, goal.event_id]
                        )
                    )
            end = off if off is not None else at
            conceded = [
                g.event_id
                for g, _ in m.goals
                if g.team_id != club.club_id and spell.on_ms <= g.match_clock_ms <= end
            ]
            if not conceded and played >= FULL_APPEARANCE_MS and CLEAN_SHEET[role]:
                items.append(
                    FantasyItem(label="Clean sheet", points=CLEAN_SHEET[role], event_ids=[])
                )
            if role in ("gk", "def") and len(conceded) >= CONCEDED_PER_POINT:
                items.append(
                    FantasyItem(
                        label=f"{len(conceded)} conceded",
                        points=-(len(conceded) // CONCEDED_PER_POINT),
                        event_ids=conceded,
                    )
                )
            saves = [e.event_id for e in events if e.type == "save" and e.player_id == player_id]
            if role == "gk" and len(saves) >= SAVES_PER_POINT:
                items.append(
                    FantasyItem(
                        label=f"{len(saves)} saves",
                        points=len(saves) // SAVES_PER_POINT,
                        event_ids=saves,
                    )
                )
            for e in events:
                if e.type == "card" and e.player_id == player_id:
                    red = e.attributes.card_color == "red"
                    items.append(
                        FantasyItem(
                            label="Red card" if red else "Yellow card",
                            points=RED if red else YELLOW,
                            event_ids=[e.event_id],
                        )
                    )
        return FantasyPlayer(
            player_id=player_id,
            name=player.name,
            number=player.number,
            role=player.role,
            club_id=club.club_id,
            match_id=m.match.match_id,
            on_pitch=on_pitch,
            points=sum(i.points for i in items),
            items=items,
        )

    def involved(self, goal: MatchEvent) -> set[str]:
        """Who earned points for a goal: the scorer, and the assist if there was one."""
        m = self.match_of.get(goal.player_id or "")
        assist = next((a for g, a in m.goals if g.event_id == goal.event_id), None) if m else None
        return {goal.player_id or ""} | ({m.assisters[assist]} if m and assist else set())

    def on_pitch(self, player_id: str, t: int) -> bool:
        spell = self.match_of[player_id].spells.get(player_id)
        return bool(spell and spell.on_ms <= t and (spell.off_ms is None or t < spell.off_ms))

    def check_xi(self, player_ids: Sequence[str]) -> list[str]:
        """What's wrong with an XI, if anything: eleven different players, one goalkeeper, three
        to five defenders, two to five midfielders, one to three forwards, at most three from a
        club."""
        problems = []
        unknown = [p for p in player_ids if p not in self.players]
        if unknown:
            return [f"Unknown players: {', '.join(unknown)}."]
        if len(set(player_ids)) != XI_SIZE:
            problems.append(f"Pick {XI_SIZE} different players.")
        names = {"gk": "goalkeeper", "def": "defenders", "mid": "midfielders", "fwd": "forwards"}
        for role, (low, high) in XI_SHAPE.items():
            n = sum(1 for p in set(player_ids) if self.players[p][0].role == role)
            if not low <= n <= high:
                span = str(low) if low == high else f"{low} to {high}"
                problems.append(f"Pick {span} {names[role]} (you have {n}).")
        clubs: dict[str, int] = {}
        for p in set(player_ids):
            club = self.players[p][1]
            clubs[club.name] = clubs.get(club.name, 0) + 1
        problems += [f"At most {PER_CLUB} from {c}." for c, n in clubs.items() if n > PER_CLUB]
        return problems


def _index(m: "ScheduledMatch") -> _Match:
    events = m.result.events
    spells: dict[str, _Spell] = {}
    for club in (m.home, m.away):
        for p in club.squad[:XI_SIZE]:
            spells[p.player_id] = _Spell(on_ms=0)
    for e in events:
        if e.type == "substitution" and e.player_id and e.target_player_id:
            if e.player_id in spells:
                spells[e.player_id].off_ms = e.match_clock_ms
                spells[e.player_id].off_event = e.event_id
            spells[e.target_player_id] = _Spell(on_ms=e.match_clock_ms, on_event=e.event_id)
        elif e.type == "card" and e.attributes.card_color == "red" and e.player_id in spells:
            spells[e.player_id].off_ms = e.match_clock_ms
            spells[e.player_id].off_event = e.event_id
    goals: list[tuple[MatchEvent, str | None]] = []
    assisters: dict[str, str] = {}
    for i, e in enumerate(events):
        if e.type != "goal":
            continue
        assist = _assist(events, i, e)
        if assist:
            assisters[assist.event_id] = assist.player_id or ""
        goals.append((e, assist.event_id if assist else None))
    return _Match(
        match=m,
        spells=spells,
        goals=goals,
        assisters=assisters,
        clocks=[e.match_clock_ms for e in events],
    )


def _assist(events: Sequence[MatchEvent], goal_index: int, goal: MatchEvent) -> MatchEvent | None:
    """The teammate's ball the scorer shot from: the last on-the-ball event before the shot, if it
    was a pass or set piece to the scorer."""
    i = goal_index - 1
    while i >= 0 and events[i].type in (*OFF_THE_BALL, "goal"):
        i -= 1
    if i < 0 or events[i].type != "shot" or events[i].player_id != goal.player_id:
        return None
    i -= 1
    while i >= 0 and events[i].type in OFF_THE_BALL:
        i -= 1
    before = events[i] if i >= 0 else None
    if (
        before
        and before.type in ASSIST_TYPES
        and before.team_id == goal.team_id
        and before.player_id != goal.player_id
        and before.target_player_id == goal.player_id
        and before.outcome in (None, "success")
    ):
        return before
    return None
