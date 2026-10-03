"""Placeholder event source for the Phase 0 walking skeleton.

Produces valid, seeded `MatchEvent`s with plausible-looking values so the stream and UI can be
built end to end. It has no football logic; the real match engine replaces it in Phase 1.
"""

import random
from collections.abc import Iterator
from itertools import count

from app.models import EventAttributes, MatchEvent
from app.models.common import PitchPoint
from app.models.events import EventType

MATCH_ID = "m_fake"
FULL_TIME_MS = 90 * 60 * 1000
_WEIGHTED_TYPES: list[tuple[EventType, int]] = [
    ("pass", 60),
    ("pressure", 12),
    ("tackle", 8),
    ("sprint", 8),
    ("possession_change", 6),
    ("shot", 4),
    ("foul", 2),
]


def fake_events(seed: int = 7) -> Iterator[MatchEvent]:
    """Yield one fake match, kickoff to full time. Same seed, same match."""
    rng = random.Random(seed)
    types, weights = zip(*_WEIGHTED_TYPES, strict=True)
    clock_ms = 0
    for n in count(1):
        if clock_ms >= FULL_TIME_MS:
            return
        event_type: EventType = "kickoff" if n == 1 else rng.choices(types, weights)[0]
        side = rng.choice(["home", "away"])
        yield MatchEvent(
            event_id=f"evt_{n:06d}",
            match_id=MATCH_ID,
            minute=clock_ms // 60_000,
            second=clock_ms // 1000 % 60,
            match_clock_ms=clock_ms,
            type=event_type,
            team_id=f"t_{side}",
            player_id=f"p_{side}_{rng.randint(1, 11):02d}",
            location=PitchPoint(x=round(rng.uniform(0, 100), 1), y=round(rng.uniform(0, 100), 1)),
            outcome="success" if rng.random() < 0.8 else "fail",
            attributes=_fake_attributes(event_type, rng),
        )
        clock_ms += rng.randint(2_000, 8_000)


def _fake_attributes(event_type: EventType, rng: random.Random) -> EventAttributes:
    match event_type:
        case "pass":
            return EventAttributes(
                pass_distance_m=round(rng.uniform(5, 45), 1),
                pass_difficulty=round(rng.random(), 2),
                ball_speed_kmh=round(rng.uniform(30, 90), 1),
            )
        case "shot":
            return EventAttributes(ball_speed_kmh=round(rng.uniform(50, 120), 1))
        case "sprint":
            return EventAttributes(
                top_speed_kmh=round(rng.uniform(25, 35), 1),
                sprint_distance_m=round(rng.uniform(10, 50), 1),
            )
        case "pressure":
            return EventAttributes(pressure_level=round(rng.random(), 2))
        case _:
            return EventAttributes()
