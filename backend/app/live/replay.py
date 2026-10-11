"""Replays: the move behind a goal or a big chance, for the channel to show when it cuts in.

A replay window starts where the move began (the scoring side's unbroken run of possession, or
the set piece it came from), and ends a moment after the shot, so the replay shows the build-up
rather than a fixed number of seconds. The shot itself is marked for slow motion. Windows never
reach past now: the endpoint clamps them, so nothing that hasn't happened leaks out.
"""

from dataclasses import dataclass
from typing import Literal

from app.models import MatchEvent

LEAD_IN_MS = 1_500  # a beat of play before the move's first touch
MIN_BUILD_UP_MS = 5_000
MAX_BUILD_UP_MS = 10_000  # a whip-around replay is short: the move, not the whole spell
AFTER_GOAL_MS = 2_500  # the ball in the net and the first reaction
AFTER_CHANCE_MS = 2_000
SLOW_BEFORE_MS = 1_200  # slow motion from just before the shot...
SLOW_AFTER_MS = 800  # ...to just after it
# Events that mean the other side had the ball, so the move starts after them.
POSSESSION_TYPES = {"pass", "shot", "tackle", "possession_change"}
RESTARTS = {"throw_in", "corner", "free_kick", "goal_kick", "kickoff", "penalty"}

Kind = Literal["goal", "chance"]


@dataclass(frozen=True)
class Window:
    kind: Kind
    shot: MatchEvent
    from_ms: int
    to_ms: int
    slow_from_ms: int
    slow_to_ms: int


def window(events: list[MatchEvent], event_id: str) -> Window | None:
    """The replay window for a goal or a shot, or None if the event isn't one."""
    index = next((i for i, e in enumerate(events) if e.event_id == event_id), None)
    if index is None or events[index].type not in ("goal", "shot"):
        return None
    target = events[index]
    kind: Kind = "goal" if target.type == "goal" else "chance"
    # A goal is logged with the shot that scored it, in the same instant: replay from the shot.
    shot_index = index
    if kind == "goal":
        shot_index = next(
            (
                i
                for i in range(index, -1, -1)
                if events[i].type == "shot" and events[i].team_id == target.team_id
            ),
            index,
        )
    shot = events[shot_index]
    start = shot.match_clock_ms
    for e in reversed(events[:shot_index]):
        if shot.match_clock_ms - e.match_clock_ms > MAX_BUILD_UP_MS:
            break
        if e.team_id != shot.team_id and e.type in POSSESSION_TYPES:
            break  # the other side had it: the move starts after this
        if e.team_id == shot.team_id:
            start = e.match_clock_ms
        if e.type in RESTARTS:
            break  # the move came from a set piece: start with it
    start = min(start - LEAD_IN_MS, shot.match_clock_ms - MIN_BUILD_UP_MS)
    start = max(0, start, shot.match_clock_ms - MAX_BUILD_UP_MS)
    end = target.match_clock_ms + (AFTER_GOAL_MS if kind == "goal" else AFTER_CHANCE_MS)
    return Window(
        kind=kind,
        shot=shot,
        from_ms=start,
        to_ms=end,
        slow_from_ms=shot.match_clock_ms - SLOW_BEFORE_MS,
        slow_to_ms=shot.match_clock_ms + SLOW_AFTER_MS,
    )
