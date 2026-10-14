"""The matchday clock: maps wall time to match time for every fixture at once.

All fixtures kick off together. The clock loops (play to full time, hold the result for a few
minutes, kick off again) so a visitor on any day finds live matches. `MATCH_START_MINUTE` sets
where the loop starts when the server boots (e.g. 55 to record a demo from the second half), and
`MATCH_SPEED` speeds it up for testing.

When nobody has read the clock for ten minutes (as long as the host waits before scaling to
zero), the next read starts the day again from `MATCH_START_MINUTE`: a server kept warm gives the
next visitor what a cold start would, without the wait.
"""

import os
import time
from collections.abc import Callable

FULL_TIME_HOLD_MS = 4 * 60_000
QUIET_RESTART_S = 10 * 60  # infra/hosting.bicep: cooldownPeriod


class MatchdayClock:
    def __init__(
        self,
        cycle_ms: int,
        start_minute: float | None = None,
        speed: float | None = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cycle_ms = cycle_ms + FULL_TIME_HOLD_MS
        self.start_ms = 60_000 * (
            start_minute
            if start_minute is not None
            else float(os.environ.get("MATCH_START_MINUTE", "55"))
        )
        self.speed = speed if speed is not None else float(os.environ.get("MATCH_SPEED", "1"))
        self._now = now
        self._started = self._last_read = now()

    def jump(self, clock_ms: int) -> None:
        """Run on from `clock_ms` (the producer's demo control: skip to the final whistle, or
        back to the start). Everyone watching jumps with it: there is one clock."""
        now = self._now()
        if self.speed:
            self._started = now - (clock_ms - self.start_ms) / 1000 / self.speed
        else:
            self.start_ms, self._started = clock_ms, now
        self._last_read = now

    def clock_ms(self) -> int:
        """Match time now, in milliseconds since kickoff, looping every cycle."""
        now = self._now()
        if now - self._last_read > QUIET_RESTART_S:
            self._started = now  # nobody watching for a while: the next visitor starts afresh
        self._last_read = now
        elapsed = (now - self._started) * 1000 * self.speed
        return int((self.start_ms + elapsed) % self.cycle_ms)
