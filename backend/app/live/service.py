"""The live matchday: simulated fixtures, played back on the matchday clock.

Built once at startup. Every view is computed for "now" on the clock, so the match centre and a
match page always agree, and nothing after the current minute leaks out.
"""

from functools import lru_cache

from app.generator.matchday import ScheduledMatch, build_matchday
from app.generator.world import Club
from app.live.clock import MatchdayClock
from app.live.copy import CopyContext
from app.live.desk import AgentBridge, ProposalDesk
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
from app.state.aggregator import event_impacts, key_moments, momentum, team_stats

RECENT_EVENTS = 40


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
        cycle = max(m.result.full_time_ms for m in self.matches)
        self.clock = clock or MatchdayClock(cycle)
        # The featured match has a human producer; every other match airs on autopilot.
        self.desks = {m.match_id: self._build_desk(m) for m in self.matches}

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


def _club(club: Club) -> ClubRef:
    return ClubRef(club_id=club.club_id, name=club.name, short=club.short, color=club.color)
