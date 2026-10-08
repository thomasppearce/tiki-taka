"""The final day of the Meridian League season: ten fixtures, all kicking off together.

Each fixture has its own seed and storyline. Three are scripted, because the title and the last
relegation place are written around their goals (app/generator/season.py): Northgate v Westmere
(the featured match, the one the full agent team covers), Brackenford v Halvern, and Corrin Bay v
Millbrook. The rest play free storylines, so the race for fourth is decided on the pitch.
"""

from dataclasses import dataclass
from functools import cache

from app.generator.engine import MatchEngine, MatchResult
from app.generator.storylines import STORYLINES, Storyline
from app.generator.world import Club, League, build_world

FEATURED_MATCH_ID = "m_l1_1"

# (home, away, storyline), by club short code.
FIXTURES: tuple[tuple[str, str, str], ...] = (
    ("NGR", "WMA", "second_half_comeback"),  # 1-0 at 23', 1-1 at 71', 1-2 from 86' (stoppage)
    ("BRK", "HVT", "late_away_winner"),  # 0-1 around 78'
    ("CRB", "MBT", "early_home_goal_holds"),  # 1-0 around 31'
    ("TDR", "IVU", "late_collapse"),
    ("KRC", "SCT", "balanced"),
    ("PHA", "ASM", "end_to_end"),
    ("GHV", "DHU", "dominant_but_wasteful"),
    ("MSB", "LPT", "balanced"),
    ("CFG", "RSR", "red_card_swing"),
    ("ELR", "CPF", "end_to_end"),
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
    """Simulate the whole final day. Cached: the same seed always gives the same matchday."""
    (league,) = build_world(seed)
    clubs = {club.short: club for club in league.clubs}
    matches = []
    for index, (home, away, story) in enumerate(FIXTURES):
        match_id = f"m_l1_{index + 1}"
        match_seed = seed * 100 + index
        storyline = STORYLINES[story]
        result = MatchEngine(match_id, clubs[home], clubs[away], storyline, match_seed).run()
        matches.append(
            ScheduledMatch(
                match_id,
                league,
                clubs[home],
                clubs[away],
                storyline,
                match_seed,
                match_id == FEATURED_MATCH_ID,
                result,
            )
        )
    return tuple(matches)
