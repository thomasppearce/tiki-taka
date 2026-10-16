"""Whose whip-around: what matters, and to whom.

The Director (app/live/channel.py) cuts the same way for everyone: pressure times stakes, goals
cut at once, a minimum dwell, an aftermath. A lens decides the stakes. The main channel weighs
what a goal would change in the whole table. A signed-in fan's own whip-around weighs what it
would change for their club, or for their fantasy XI, and says so in a line "for you".

Lenses are code, not models: a fan's whip-around shares the Watchers' stories with the channel,
so it costs no extra model calls however many fans are watching.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

from app.generator.matchday import ScheduledMatch
from app.generator.world import Player
from app.models.channel import Lens as LensInfo
from app.models.channel import LensKind
from app.models.events import MatchEvent
from app.models.table import LeagueTable
from app.state.stories import boot_stake
from app.state.table import ZONE_WEIGHT, Change, Placed, Scores, standings, summarize

if TYPE_CHECKING:
    from app.live.service import MatchdayService

OWN_MATCH = 0.5  # a goal in your club's own match always matters
PER_PLACE = 0.15  # moving a place without changing zone matters a little...
MAX_PLACES = 3  # ...up to three places
SCORING_ROLE = {"fwd": 0.6, "mid": 0.4, "def": 0.0, "gk": 0.0}  # could score (defenders: see below)
CLEAN_SHEET_AT_RISK = 0.3  # your keeper or defender could concede (their goals still cut)
MAX_STAKE = 1.5
OUT_OF = {
    "champions": "off the top",
    "continental": "out of the top four",
    "relegation": "out of the relegation zone",
}
ZONE_WORDS = {
    "continental": "in the continental cup places",
    "relegation": "in the relegation zone",
}


class Lens(Protocol):
    kind: LensKind
    key: str

    def stake(
        self, m: ScheduledMatch, club_id: str, t: int, table: LeagueTable
    ) -> tuple[float, str | None]:
        """What a goal for `club_id` in `m` would change, as a weight and a sentence."""
        ...

    def goal_weight(self, match_id: str, goal: MatchEvent) -> float:
        """1: cut to it now, even in another goal's aftermath. Above 0: cut unless in one."""
        ...

    def for_you(self, match_id: str, t: int) -> str | None: ...

    def info(self, t: int) -> LensInfo: ...


class ChannelLens:
    """Everyone's channel: what a goal would change in the whole table."""

    kind: LensKind = "channel"
    key = "channel"

    def __init__(self, service: "MatchdayService") -> None:
        self.service = service

    def stake(
        self, m: ScheduledMatch, club_id: str, t: int, table: LeagueTable
    ) -> tuple[float, str | None]:
        """What a goal would change in the table, and in the Golden Boot race."""
        stake = next(
            (x for x in table.stakes if x.match_id == m.match_id and x.scorer_club_id == club_id),
            None,
        )
        boot, boot_summary = boot_stake(self.service, club_id, t)
        parts = [x for x in (stake.summary if stake else None, boot_summary) if x]
        return (stake.weight if stake else 0.0) + boot, ("; ".join(parts) or None)

    def goal_weight(self, match_id: str, goal: MatchEvent) -> float:
        swing = any(x.event_id == goal.event_id for x in self.service.swings)
        return 1.0 if swing else 0.5

    def for_you(self, match_id: str, t: int) -> str | None:
        return None

    def info(self, t: int) -> LensInfo:
        return LensInfo(kind="channel")


JUST_SCORED_MS = 60_000  # a goal this recent is still the news on a fan's channel


class ClubLens:
    """A fan's club: what a goal anywhere would do to their club's place in the table."""

    kind: LensKind = "club"

    def __init__(self, service: "MatchdayService", club_id: str) -> None:
        self.service = service
        self.club_id = club_id
        self.key = f"club:{club_id}"
        self.name = service.club(club_id).name
        self.match_id = next(
            m.match_id for m in service.matches if club_id in (m.home.club_id, m.away.club_id)
        )
        self._memo: tuple[int, Scores, list[Placed]] | None = None

    def stake(
        self, m: ScheduledMatch, club_id: str, t: int, table: LeagueTable
    ) -> tuple[float, str | None]:
        scores, now = self._now(t)
        before = self._place(now)
        after_table = standings(self.service.season, _plus_goal(scores, m, club_id))
        after = self._place(after_table)
        own = OWN_MATCH if m.match_id == self.match_id else 0.0
        if before.position == after.position:
            return own, None
        change = Change(self.club_id, before.position, after.position, before.zone, after.zone)
        if before.zone != after.zone:
            weight = max(ZONE_WEIGHT[z] for z in (before.zone, after.zone) if z)
        else:
            weight = PER_PLACE * min(MAX_PLACES, abs(before.position - after.position))
        sentence = summarize([change], after_table, self.service._names).rstrip(".")
        return min(MAX_STAKE, own + weight), sentence

    def goal_weight(self, match_id: str, goal: MatchEvent) -> float:
        if match_id == self.match_id:
            return 1.0
        season = self.service.season
        before = self._place(standings(season, self.service._scores(goal.match_clock_ms - 1)))
        after = self._place(standings(season, self.service._scores(goal.match_clock_ms)))
        if before.zone != after.zone:
            return 1.0
        return 0.5 if before.position != after.position else 0.0

    def for_you(self, match_id: str, t: int) -> str | None:
        m = self.service.by_id[match_id]
        moved = self._moved_by_goal(m, t)  # a goal that just moved them, here or elsewhere
        if moved:
            return f"That goal: {moved}."
        here = self._place(self._now(t)[1])
        if match_id == self.match_id:
            where = _ordinal(here.position)
            if here.zone == "champions":
                where = "top"
            elif here.zone:
                where += f", {ZONE_WORDS[here.zone]}"
            else:  # out of a zone they were in today: that's the news
                left = next(
                    (
                        c
                        for swing in reversed(self.service.swings)
                        if swing.match_clock_ms <= t
                        for c in swing.changes
                        if c.club_id == self.club_id
                    ),
                    None,
                )
                if left and left.from_zone and not left.to_zone:
                    where += f", {OUT_OF[left.from_zone]}"
            return f"{self.name}'s match. As it stands, {self.name} are {where}."
        table = self.service._table(t // 1000)
        options = [(*self.stake(m, side.club_id, t, table), side.name) for side in (m.home, m.away)]
        weight, sentence, scorer = max(options, key=lambda o: o[0])
        return f"A goal for {scorer}: {sentence}." if sentence else None

    def _moved_by_goal(self, m: ScheduledMatch, t: int) -> str | None:
        """What a goal in the last minute, in their match or another, did to the fan's club: the
        line a winner deserves ("Corrin Bay drop into the relegation zone"), or None."""
        goal = next(
            (
                e
                for e in reversed(m.result.events)
                if e.type == "goal" and t - JUST_SCORED_MS <= e.match_clock_ms <= t
            ),
            None,
        )
        if goal is None:
            return None
        season = self.service.season
        before = self._place(standings(season, self.service._scores(goal.match_clock_ms - 1)))
        after_table = standings(season, self.service._scores(goal.match_clock_ms))
        after = self._place(after_table)
        if before.position == after.position:
            return None
        change = Change(self.club_id, before.position, after.position, before.zone, after.zone)
        return summarize([change], after_table, self.service._names).rstrip(".")

    def info(self, t: int) -> LensInfo:
        return LensInfo(kind="club", club_id=self.club_id)

    def _now(self, t: int) -> tuple[Scores, list[Placed]]:
        """Today's scores and the table as it stands, worked out once per match second (rounded
        up, so a goal earlier in this second counts: a last-second winner moves the table)."""
        second = -(-t // 1000)
        if self._memo is None or self._memo[0] != second:
            scores = self.service._scores(second * 1000)
            self._memo = (second, scores, standings(self.service.season, scores))
        return self._memo[1], self._memo[2]

    def _place(self, table: list[Placed]) -> Placed:
        return next(p for p in table if p.record.club_id == self.club_id)


class FantasyLens:
    """A fan's fantasy XI: where their players are about to score, or to concede."""

    kind: LensKind = "fantasy"

    def __init__(self, service: "MatchdayService", xi: list[str]) -> None:
        self.service = service
        self.fantasy = service.fantasy
        self.xi = sorted(xi)
        self.key = "xi:" + ",".join(self.xi)

    def stake(
        self, m: ScheduledMatch, club_id: str, t: int, table: LeagueTable
    ) -> tuple[float, str | None]:
        scorers, keepers = [], []
        for pid in self.xi:
            player, club = self.fantasy.players[pid]
            if self.fantasy.match_of[pid].match.match_id != m.match_id:
                continue
            if not self.fantasy.on_pitch(pid, t):
                continue
            if club.club_id == club_id and SCORING_ROLE[player.role]:
                scorers.append(player)
            elif club.club_id != club_id and player.role in ("gk", "def"):
                keepers.append(player)
        weight = sum(SCORING_ROLE[p.role] for p in scorers) + CLEAN_SHEET_AT_RISK * len(keepers)
        parts = []
        if scorers:
            parts.append(f"{_names(scorers)} could score")
        if keepers:
            parts.append(f"{_names(keepers)} could lose a clean sheet")
        return min(MAX_STAKE, weight), ("; ".join(parts) or None)

    def goal_weight(self, match_id: str, goal: MatchEvent) -> float:
        involved = self.fantasy.involved(goal)
        if involved & set(self.xi):
            return 1.0
        conceding = [
            pid
            for pid in self.xi
            if self.fantasy.match_of[pid].match.match_id == match_id
            and self.fantasy.players[pid][1].club_id != goal.team_id
            and self.fantasy.players[pid][0].role in ("gk", "def")
            and self.fantasy.on_pitch(pid, goal.match_clock_ms)
        ]
        return 0.5 if conceding else 0.0

    def for_you(self, match_id: str, t: int) -> str | None:
        here = [
            self.fantasy.score(pid, t)
            for pid in self.xi
            if self.fantasy.match_of[pid].match.match_id == match_id
        ]
        if not here:
            return None
        here.sort(key=lambda p: -p.points)
        listed = ", ".join(f"{p.name.split(' ', 1)[-1]} {p.points} pts" for p in here)
        return f"Your XI here: {listed}."

    def info(self, t: int) -> LensInfo:
        xi = [self.fantasy.score(pid, t) for pid in self.xi]
        order = {"gk": 0, "def": 1, "mid": 2, "fwd": 3}
        xi.sort(key=lambda p: (order[p.role], -p.points, p.name))
        return LensInfo(kind="fantasy", xi=xi, points=sum(p.points for p in xi))


def lens_for(service: "MatchdayService", key: str | None) -> Lens:
    """A lens from its key: none or "channel", "club:<club_id>", or "xi:<11 player ids>"."""
    if not key or key == "channel":
        return ChannelLens(service)
    kind, _, rest = key.partition(":")
    if kind == "club":
        if rest not in service.clubs:
            raise ValueError(f"No club {rest}.")
        return ClubLens(service, rest)
    if kind == "xi":
        xi = [p for p in rest.split(",") if p]
        problems = service.fantasy.check_xi(xi)
        if problems:
            raise ValueError(" ".join(problems))
        return FantasyLens(service, xi)
    raise ValueError(f"Unknown lens {key!r}: use club:<club_id> or xi:<player ids>.")


def _plus_goal(scores: Scores, m: ScheduledMatch, scorer_id: str) -> Scores:
    after = dict(scores)
    other = m.away.club_id if scorer_id == m.home.club_id else m.home.club_id
    s, c = after[scorer_id]
    after[scorer_id] = (s + 1, c)
    o_s, o_c = after[other]
    after[other] = (o_s, o_c + 1)
    return after


def _names(players: Sequence[Player]) -> str:
    names = [p.name.split(" ", 1)[-1] for p in players]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
