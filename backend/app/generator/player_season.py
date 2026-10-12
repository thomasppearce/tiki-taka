"""The players' season so far, and the personal stories the final day can settle.

Synthetic, like the table (season.py), and written to set up the day. Every club's players'
goals add up to its goals in the season table; assists and appearances are shared out the same
way, by role and ability. The stories are curated around goals the story pins (storylines.py),
so they come true on the day whatever else happens:

- The Golden Boot: Ambrose (Halvern) and Desai (Westmere) start level on 22, Marlow (Northgate)
  on 21. Marlow's early goal makes it a three-way tie, Desai's equaliser puts him top, Ambrose's
  title goal draws level again, and Desai's stoppage-time winner, the goal that keeps Westmere up,
  wins it. Nobody else is within reach (17 at most).
- Radcliffe is one short of 100 league goals for Corrin Bay; he scores on the day.
- Marlow faces Westmere, the club he left for Northgate last summer, and scores against them.
- Jervaise, Halvern's captain, retires after the final day: his last game is the title decider.
- Mistral Bay v Lanterne Port FC is the Coast derby.

Code-written, so the agents can cite every number and the checker can hold them to it.
"""

import random
from collections.abc import Iterable
from dataclasses import dataclass

from app.generator.season import table_before_final_day
from app.generator.world import Club

GOLDEN_BOOT: dict[str, int] = {"p_hvt_09": 22, "p_wma_09": 22, "p_ngr_10": 21}
OTHERS_MAX = 17  # nobody else is within reach of the Golden Boot, even with a hat-trick
ROLE_GOALS = {"fwd": 1.0, "mid": 0.55, "def": 0.15, "gk": 0.0}
ROLE_ASSISTS = {"fwd": 0.7, "mid": 1.0, "def": 0.35, "gk": 0.02}
BENCH = 0.35  # substitutes play less, so score and make less
ASSISTS_PER_GOAL = 0.7


@dataclass(frozen=True)
class PlayerSeason:
    player_id: str
    goals: int
    assists: int
    appearances: int


@dataclass(frozen=True)
class Milestone:
    """A round number a player is close to: `goals` league goals for their club so far."""

    player_id: str
    goals: int
    target: int


@dataclass(frozen=True)
class Farewell:
    player_id: str
    seasons: int


@dataclass(frozen=True)
class FormerClub:
    player_id: str
    former_club_id: str


@dataclass(frozen=True)
class Derby:
    home_id: str
    away_id: str
    name: str


MILESTONES = (Milestone("p_crb_11", goals=99, target=100),)  # Radcliffe
FAREWELLS = (Farewell("p_hvt_02", seasons=14),)  # Jervaise
FORMER_CLUBS = (FormerClub("p_ngr_10", former_club_id="t_wma"),)  # Marlow
DERBIES = (Derby("t_msb", "t_lpt", "the Coast derby"),)


def season_records(clubs: Iterable[Club], seed: int = 2026) -> dict[str, PlayerSeason]:
    """Every player's season before the final day, adding up to each club's season totals."""
    table = {r.club_id: r for r in table_before_final_day()}
    out: dict[str, PlayerSeason] = {}
    for club in clubs:
        rng = random.Random(f"{seed}:{club.club_id}:season")
        record = table[club.club_id]
        goals = _goals(club, record.goals_for)
        assists = _share(
            round(record.goals_for * ASSISTS_PER_GOAL),
            {
                p.player_id: ROLE_ASSISTS[p.role]
                * (0.3 + p.passing) ** 2
                * (1 if i < 11 else BENCH)
                for i, p in enumerate(club.squad)
            },
            cap=None,
        )
        for i, p in enumerate(club.squad):
            apps = rng.randint(29, 37) if i < 11 else rng.randint(6, 24)
            out[p.player_id] = PlayerSeason(
                p.player_id, goals.get(p.player_id, 0), assists[p.player_id], apps
            )
    return out


def _goals(club: Club, total: int) -> dict[str, int]:
    fixed = {
        p.player_id: GOLDEN_BOOT[p.player_id] for p in club.squad if p.player_id in GOLDEN_BOOT
    }
    weights = {
        p.player_id: ROLE_GOALS[p.role] * (0.3 + p.finishing) * (1 if i < 11 else BENCH)
        for i, p in enumerate(club.squad)
        if p.player_id not in fixed
    }
    return {**fixed, **_share(total - sum(fixed.values()), weights, cap=OTHERS_MAX)}


def _share(total: int, weights: dict[str, float], cap: int | None) -> dict[str, int]:
    """Split `total` in proportion to `weights` (largest remainders), nobody above `cap`."""
    shares = dict.fromkeys(weights, 0)
    open_ = {k: w for k, w in weights.items() if w > 0}
    left = total
    while left > 0 and open_:
        whole = sum(open_.values())
        exact = {k: left * w / whole for k, w in open_.items()}
        given = {k: int(v) for k, v in exact.items()}
        remainder = left - sum(given.values())
        for k in sorted(exact, key=lambda k: (-(exact[k] - given[k]), k))[:remainder]:
            given[k] += 1
        left = 0
        for k, n in given.items():
            room = n if cap is None else min(n, cap - shares[k])
            shares[k] += room
            left += n - room
        open_ = {k: w for k, w in open_.items() if cap is None or shares[k] < cap}
    return shares
