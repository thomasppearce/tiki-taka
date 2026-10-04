"""API views of the matchday: the match centre and one match in detail."""

from typing import Literal

from pydantic import Field

from app.models.common import Contract
from app.models.events import MatchEvent
from app.models.insight import EventImpact, KeyMoment, TeamStats

MatchStatus = Literal["live", "full_time"]
Role = Literal["gk", "def", "mid", "fwd"]


class ClubRef(Contract):
    club_id: str
    name: str
    short: str
    color: str  # brand color: crests and scorebug strips only


class PlayerRef(Contract):
    player_id: str
    club_id: str
    name: str
    number: int
    role: Role


class MatchCard(Contract):
    """One match on the match centre: score, clock, a momentum ribbon, and its biggest moment."""

    match_id: str
    league_id: str
    league_name: str
    home: ClubRef
    away: ClubRef
    score_home: int = Field(ge=0)
    score_away: int = Field(ge=0)
    clock_ms: int = Field(ge=0)
    status: MatchStatus
    featured: bool
    momentum: list[float]
    top_moment: KeyMoment | None = None


class LeagueGroup(Contract):
    league_id: str
    name: str
    matches: list[MatchCard]


class Matchday(Contract):
    clock_ms: int = Field(ge=0)
    leagues: list[LeagueGroup]


class MatchDetail(Contract):
    """Everything needed to open a match: the card, stats, key moments, squads, and recent play."""

    card: MatchCard
    home_stats: TeamStats
    away_stats: TeamStats
    key_moments: list[KeyMoment]
    players: list[PlayerRef]
    recent_events: list[MatchEvent]
    impacts: list[EventImpact]
