"""One matchday: 3 fictional leagues x 4 fixtures, each with its own seed and storyline.

The featured fixture (Northgate Rovers v Westmere Athletic) is the one the full agent team
covers; the rest feed the match centre through the deterministic aggregator only.
"""

from dataclasses import dataclass
from functools import cache

from app.generator.engine import MatchEngine, MatchResult
from app.generator.storylines import STORYLINES, Storyline
from app.generator.world import Club, League, build_world

FEATURED_MATCH_ID = "m_l1_1"

# Storylines for the non-featured fixtures, assigned in order so every matchday tells a mix.
_ROTATION = (
    "balanced",
    "end_to_end",
    "late_collapse",
    "dominant_but_wasteful",
    "red_card_swing",
    "balanced",
    "end_to_end",
    "balanced",
    "late_collapse",
    "dominant_but_wasteful",
    "balanced",
)


@dataclass(frozen=True)
class ScheduledMatch:
    match_id: str
    league: League
    home: Club
    away: Club
    storyline: Storyline
    seed: int
    featured: bool
    result: MatchResult


@cache
def build_matchday(seed: int = 2026) -> tuple[ScheduledMatch, ...]:
    """Simulate the whole matchday. Cached: the same seed always gives the same matchday."""
    matches = []
    rotation = iter(_ROTATION)
    for league in build_world(seed):
        clubs = league.clubs
        for fixture in range(4):
            home, away = clubs[fixture * 2], clubs[fixture * 2 + 1]
            match_id = f"m_l{league.league_id[2:]}_{fixture + 1}"
            featured = match_id == FEATURED_MATCH_ID
            storyline = STORYLINES["second_half_comeback" if featured else next(rotation)]
            match_seed = seed * 100 + len(matches)
            result = MatchEngine(match_id, home, away, storyline, match_seed).run()
            matches.append(
                ScheduledMatch(
                    match_id, league, home, away, storyline, match_seed, featured, result
                )
            )
    return tuple(matches)
