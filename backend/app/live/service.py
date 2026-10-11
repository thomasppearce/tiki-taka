"""The live matchday: simulated fixtures, played back on the matchday clock.

Built once at startup. Every view is computed for "now" on the clock, so the match centre and a
match page always agree, and nothing after the current minute leaks out.
"""

import threading
from collections import OrderedDict
from functools import lru_cache

from app.generator.matchday import ScheduledMatch, build_matchday
from app.generator.season import TEAM_OF_THE_SEASON, table_before_final_day
from app.generator.world import Club
from app.live.channel import ChannelDirector
from app.live.clock import MatchdayClock
from app.live.copy import CopyContext
from app.live.desk import AgentBridge, ProposalDesk
from app.live.lens import lens_for
from app.live.replay import window
from app.models.channel import Squads
from app.models.desk import Desk
from app.models.insight import EventImpact, KeyMoment
from app.models.matchday import (
    ClubRef,
    LeagueGroup,
    MatchCard,
    Matchday,
    MatchDetail,
    PlayerRef,
)
from app.models.replay import Replay
from app.models.table import LeagueTable, Stake, TableRow, TableSwing, ZoneChange
from app.state.aggregator import event_impacts, key_moments, momentum, team_stats
from app.state.fantasy import RULES, FantasyScorer
from app.state.table import Change, Scores, standings, summarize, weight, zone_changes

RECENT_EVENTS = 40
MAX_WHIPS = 200  # fans' own whip-arounds kept in memory, least recently watched dropped first
REPLAY_FRAME_MS = 250  # replays carry frames at the live stream's 4 Hz


class MatchdayService:
    def __init__(
        self,
        seed: int = 2026,
        clock: MatchdayClock | None = None,
        agents: AgentBridge | None = None,
    ) -> None:
        self.agents = agents  # the agent team, for the featured match only
        self.matches = build_matchday(seed)
        self.by_id = {m.match_id: m for m in self.matches}
        self.impacts: dict[str, dict[str, EventImpact]] = {
            m.match_id: event_impacts(m.result.events, m.home.club_id) for m in self.matches
        }
        self.clubs: dict[str, Club] = {}
        self.surnames: dict[str, str] = {}
        for m in self.matches:
            for club in (m.home, m.away):
                self.clubs[club.club_id] = club
                for p in club.squad:
                    self.surnames[p.player_id] = p.name.split(" ", 1)[-1]
        self.season = table_before_final_day()
        self.swings = self._all_swings()
        cycle = max(m.result.full_time_ms for m in self.matches)
        self.clock = clock or MatchdayClock(cycle)
        # The featured match has a human producer; every other match airs on autopilot.
        self.desks = {m.match_id: self._build_desk(m) for m in self.matches}
        # The whip-around: one feed across all ten matches, and each signed-in fan's own.
        self.fantasy = FantasyScorer(self.matches)
        self.channel = ChannelDirector(self)
        self._whips: OrderedDict[str, ChannelDirector] = OrderedDict()
        self._whips_lock = threading.Lock()

    def whip(self, lens: str | None) -> ChannelDirector:
        """The channel, or a fan's own whip-around: `club:<club_id>` or `xi:<11 player ids>`.
        Raises ValueError for a lens that isn't valid (an unknown club, an XI that breaks the
        rules)."""
        if not lens or lens == "channel":
            return self.channel
        made = lens_for(self, lens)
        with self._whips_lock:
            director = self._whips.get(made.key)
            if director is None:
                director = ChannelDirector(self, lens=made, shared=self.channel)
                self._whips[made.key] = director
                while len(self._whips) > MAX_WHIPS:
                    self._whips.popitem(last=False)
            self._whips.move_to_end(made.key)
            return director

    def squads(self) -> Squads:
        """Every player, for picking a fantasy XI, with the team of the season to start from."""
        players = [
            PlayerRef(
                player_id=p.player_id, club_id=c.club_id, name=p.name, number=p.number, role=p.role
            )
            for c in sorted(self.clubs.values(), key=lambda c: c.name)
            for p in c.squad
        ]
        return Squads(players=players, suggested_xi=list(TEAM_OF_THE_SEASON), rules=RULES)

    def surname(self, player_id: str | None) -> str:
        return self.surnames.get(player_id or "", "?")

    def short(self, team_id: str | None) -> str:
        return self.clubs[team_id].short if team_id in self.clubs else "?"

    def club(self, team_id: str | None) -> Club:
        return self.clubs[team_id or ""]

    def now(self, match: ScheduledMatch) -> int:
        """This match's clock: the matchday clock, held at full time once the match ends."""
        return min(self.clock.clock_ms(), match.result.full_time_ms)

    def matchday(self) -> Matchday:
        leagues: dict[str, LeagueGroup] = {}
        for m in self.matches:
            group = leagues.setdefault(
                m.league.league_id,
                LeagueGroup(league_id=m.league.league_id, name=m.league.name, matches=[]),
            )
            group.matches.append(self.card(m.match_id))
        return Matchday(clock_ms=self.clock.clock_ms(), leagues=list(leagues.values()))

    def card(self, match_id: str) -> MatchCard:
        m = self.by_id[match_id]
        at = self.now(m)
        moments = self._moments(match_id, at // 1000)
        home, away = m.result.score_at(at)
        return MatchCard(
            match_id=m.match_id,
            league_id=m.league.league_id,
            league_name=m.league.name,
            home=_club(m.home),
            away=_club(m.away),
            score_home=home,
            score_away=away,
            clock_ms=at,
            status="full_time" if at >= m.result.full_time_ms else "live",
            featured=m.featured,
            momentum=self._momentum(match_id, at // 1000),
            top_moment=max(moments, key=lambda k: (k.importance, k.match_clock_ms), default=None),
        )

    def detail(self, match_id: str) -> MatchDetail:
        m = self.by_id[match_id]
        at = self.now(m)
        impacts = self.impacts[match_id]
        events = m.result.events
        seen = [e for e in events if e.match_clock_ms <= at]
        recent = seen[-RECENT_EVENTS:]
        return MatchDetail(
            card=self.card(match_id),
            home_stats=team_stats(events, impacts, m.home.club_id, m.home.club_id, at),
            away_stats=team_stats(events, impacts, m.away.club_id, m.home.club_id, at),
            key_moments=self._moments(match_id, at // 1000),
            players=[
                PlayerRef(
                    player_id=p.player_id,
                    club_id=club.club_id,
                    name=p.name,
                    number=p.number,
                    role=p.role,
                )
                for club in (m.home, m.away)
                for p in club.squad
            ],
            recent_events=recent,
            impacts=[impacts[e.event_id] for e in recent],
        )

    def table(self) -> LeagueTable:
        """The league as it stands now, the day's swings so far, and what is at stake."""
        return self._table(self.clock.clock_ms() // 1000)

    @lru_cache(maxsize=64)  # noqa: B019
    def _table(self, second: int) -> LeagueTable:
        now = second * 1000
        scores = self._scores(now)
        table = standings(self.season, scores)
        start = {p.record.club_id: p.position for p in standings(self.season, {})}
        playing = {c.club_id: m for m in self.matches for c in (m.home, m.away)}
        rows = []
        for p in table:
            club_id = p.record.club_id
            scored, conceded = scores[club_id]
            rows.append(
                TableRow(
                    position=p.position,
                    club=_club(self.clubs[club_id]),
                    played=p.record.played,
                    won=p.record.won,
                    drawn=p.record.drawn,
                    lost=p.record.lost,
                    goals_for=p.record.goals_for,
                    goals_against=p.record.goals_against,
                    goal_difference=p.record.goal_difference,
                    points=p.record.points,
                    zone=p.zone,
                    start_position=start[club_id],
                    match_id=playing[club_id].match_id,
                    result=(
                        "winning"
                        if scored > conceded
                        else "drawing" if scored == conceded else "losing"
                    ),
                )
            )
        stakes = []
        for m in self.matches:
            if self.now(m) >= m.result.full_time_ms:
                continue
            for scorer, other in ((m.home, m.away), (m.away, m.home)):
                after = dict(scores)
                s, c = after[scorer.club_id]
                after[scorer.club_id] = (s + 1, c)
                o_s, o_c = after[other.club_id]
                after[other.club_id] = (o_s, o_c + 1)
                changes = zone_changes(table, standings(self.season, after))
                if changes:
                    stakes.append(
                        Stake(
                            match_id=m.match_id,
                            scorer_club_id=scorer.club_id,
                            changes=[_change(c) for c in changes],
                            summary=summarize(changes, standings(self.season, after), self._names),
                            weight=weight(changes),
                        )
                    )
        return LeagueTable(
            clock_ms=now,
            rows=rows,
            swings=[s for s in self.swings if s.match_clock_ms <= now],
            stakes=sorted(stakes, key=lambda s: -s.weight),
        )

    def _scores(self, now: int) -> Scores:
        """Every club's goals scored and conceded today, as it stands at `now`."""
        scores: dict[str, tuple[int, int]] = {}
        for m in self.matches:
            home, away = m.result.score_at(min(now, m.result.full_time_ms))
            scores[m.home.club_id] = (home, away)
            scores[m.away.club_id] = (away, home)
        return scores

    @property
    def _names(self) -> dict[str, str]:
        return {club_id: club.name for club_id, club in self.clubs.items()}

    def _all_swings(self) -> list[TableSwing]:
        """Every goal of the day that moved a club into or out of a zone, in time order."""
        goals = sorted(
            (
                (e.match_clock_ms, m, e)
                for m in self.matches
                for e in m.result.events
                if e.type == "goal"
            ),
            key=lambda g: g[0],
        )
        swings = []
        for clock_ms, m, e in goals:
            before = standings(self.season, self._scores(clock_ms - 1))
            after = standings(self.season, self._scores(clock_ms))
            changes = zone_changes(before, after)
            if changes:
                swings.append(
                    TableSwing(
                        match_clock_ms=clock_ms,
                        match_id=m.match_id,
                        event_id=e.event_id,
                        changes=[_change(c) for c in changes],
                        summary=summarize(changes, after, self._names),
                    )
                )
        return swings

    def replay(self, match_id: str, event_id: str) -> Replay | None:
        """The move behind a goal or a shot that has happened, as frames and events. None if the
        event isn't a goal or shot, or hasn't happened yet."""
        m = self.by_id[match_id]
        now = self.now(m)
        events = [e for e in m.result.events if e.match_clock_ms <= now]
        w = window(events, event_id)
        if w is None:
            return None
        to_ms = min(w.to_ms, now)
        shooter = self.surname(w.shot.player_id)
        club = self.club(w.shot.team_id).name
        label = {
            "goal": f"{shooter} scores for {club}",
            "saved": f"{shooter} forces a save",
            "blocked": f"{shooter}'s shot is blocked",
        }.get("goal" if w.kind == "goal" else (w.shot.outcome or ""), f"{shooter} goes close")
        return Replay(
            match_id=match_id,
            event_id=event_id,
            kind=w.kind,
            label=label,
            as_it_stands=next(
                (f"As it stands: {s.summary}" for s in self.swings if s.event_id == event_id),
                None,
            ),
            from_ms=w.from_ms,
            to_ms=to_ms,
            slow_from_ms=w.slow_from_ms,
            slow_to_ms=min(w.slow_to_ms, to_ms),
            shooter_id=w.shot.player_id,
            frames=[
                m.result.frames.frame_at(t) for t in range(w.from_ms, to_ms + 1, REPLAY_FRAME_MS)
            ],
            events=[e for e in events if w.from_ms <= e.match_clock_ms <= to_ms],
        )

    def desk(self, match_id: str) -> Desk:
        return self.desks[match_id].snapshot(self.now(self.by_id[match_id]))

    def _build_desk(self, m: ScheduledMatch) -> ProposalDesk:
        impacts = self.impacts[m.match_id]
        events = m.result.events
        moments = key_moments(
            events, impacts, m.home.club_id, m.result.full_time_ms, self.surname, self.short
        )
        ctx = CopyContext(
            events={e.event_id: e for e in events},
            impacts=impacts,
            home_id=m.home.club_id,
            surname=self.surname,
            club=self.club,
            score_at=m.result.score_at,
        )
        return ProposalDesk(
            m, moments, ctx, autopilot=not m.featured, agents=self.agents if m.featured else None
        )

    # Cached per match and per second of match time: views are recomputed at most once a second.

    @lru_cache(maxsize=256)  # noqa: B019 - one service per process; the cache dies with it
    def _moments(self, match_id: str, second: int) -> list[KeyMoment]:
        m = self.by_id[match_id]
        return key_moments(
            m.result.events,
            self.impacts[match_id],
            m.home.club_id,
            second * 1000,
            self.surname,
            self.short,
        )

    @lru_cache(maxsize=256)  # noqa: B019
    def _momentum(self, match_id: str, second: int) -> list[float]:
        m = self.by_id[match_id]
        return momentum(m.result.events, self.impacts[match_id], m.home.club_id, second * 1000)


def _change(c: Change) -> ZoneChange:
    return ZoneChange(
        club_id=c.club_id,
        from_position=c.from_position,
        to_position=c.to_position,
        from_zone=c.from_zone,
        to_zone=c.to_zone,
    )


def _club(club: Club) -> ClubRef:
    return ClubRef(club_id=club.club_id, name=club.name, short=club.short, color=club.color)
