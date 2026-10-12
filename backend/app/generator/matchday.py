"""The final day of the Meridian League season: ten fixtures, all kicking off together.

Each fixture has its own seed and storyline. Three are scripted, because the title and the last
relegation place are written around their goals (app/generator/season.py): Northgate v Westmere
(the featured match, the one the full agent team covers), Brackenford v Halvern, and Corrin Bay v
Millbrook. The rest play free storylines, so the race for fourth is decided on the pitch.
"""

import hashlib
import os
import pickle
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from app.generator.engine import MatchEngine, MatchResult
from app.generator.storylines import STORYLINES, Storyline
from app.generator.world import Club, League, build_world

FEATURED_MATCH_ID = "m_l1_1"

# (home, away, storyline), by club short code.
FIXTURES: tuple[tuple[str, str, str], ...] = (
    ("NGR", "WMA", "second_half_comeback"),  # 1-0 at 23', 1-1 at 71', 1-2 in stoppage time
    ("BRK", "HVT", "late_away_winner"),  # 0-1 around 78'
    ("CRB", "MBT", "early_home_goal_holds"),  # 1-0 around 31' (Radcliffe)
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
    """Simulate the whole final day. Cached: the same seed always gives the same matchday. With
    MATCHDAY_CACHE_DIR set it is also kept on disk (simulating takes ~15 s, loading 0.2 s), keyed
    by the generator's own source so a change to the engine never loads a stale day. The
    container image bakes it in at build time, so a cold start is quick."""
    directory = os.environ.get("MATCHDAY_CACHE_DIR")
    path = Path(directory) / f"matchday-{seed}-{_source_hash()}.pkl" if directory else None
    if path and path.exists():
        with path.open("rb") as f:
            loaded: tuple[ScheduledMatch, ...] = pickle.load(f)  # noqa: S301 - our own file
            return loaded
    matches = _simulate(seed)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".tmp")
        partial.write_bytes(pickle.dumps(matches, protocol=pickle.HIGHEST_PROTOCOL))
        partial.replace(path)
    return matches


def _source_hash() -> str:
    """The generator's and the models' source: what a stored matchday was made with."""
    root = Path(__file__).resolve().parent.parent
    digest = hashlib.sha1()
    for folder in ("generator", "models"):
        for file in sorted((root / folder).glob("*.py")):
            digest.update(file.read_bytes())
    return digest.hexdigest()[:12]


def _simulate(seed: int) -> tuple[ScheduledMatch, ...]:
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


def fingerprint(matches: Sequence[ScheduledMatch]) -> str:
    """A short hash of the day's key events. Anything cached against the matchday (the agents'
    runs) is only reused while this is unchanged, so a change to the engine retires it."""
    digest = hashlib.sha1()
    for m in matches:
        for e in m.result.events:
            if e.type in ("goal", "shot", "card", "penalty", "substitution"):
                digest.update(f"{e.event_id}:{e.type}:{e.match_clock_ms}:{e.player_id}".encode())
    return digest.hexdigest()[:12]


if __name__ == "__main__":  # bake: MATCHDAY_CACHE_DIR=... python -m app.generator.matchday
    if not os.environ.get("MATCHDAY_CACHE_DIR"):
        raise SystemExit("Set MATCHDAY_CACHE_DIR to bake the matchday to disk.")
    # Through the real module, so the pickle names its classes app.generator.matchday.*
    from app.generator.matchday import build_matchday as bake

    bake()
    print(f"Baked the matchday into {os.environ['MATCHDAY_CACHE_DIR']}")
