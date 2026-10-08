"""The whip-around channel: one feed, ten matches, and a Director deciding where to cut.

Every second the Director scores each live match on two things: is something about to happen
(pressure: the threat a side has created in the last few minutes, decaying, with shots weighted
up) and does it matter (stakes: what a goal for that side would change in the table right now,
from app/state/table.py). A goal anywhere is an immediate cut. Otherwise the feed moves when
another match clearly deserves the screen more, and never sooner than a minimum dwell, so it
doesn't flicker between games.

Cuts are proposed with a short countdown and then taken automatically; the producer can take a
cut early, cut to any match, hold automatic cuts, or pin the feed to one match. Every cut comes
with a package (why we're here, what's at stake, the story so far), written here by code from
cited events; the agent team rewrites it when it is connected (app/agents).

Like the proposal desk, the channel only advances when someone asks for it (the channel stream
or an API call), one second at a time, so its decisions don't depend on how often it is polled.
"""

import math
import threading
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.models import Claim, MatchEvent
from app.models.channel import (
    Channel,
    Cut,
    CutPackage,
    CutReason,
    DecidedBy,
    MatchSignal,
    PendingCut,
    SideSignal,
)
from app.models.table import LeagueTable

if TYPE_CHECKING:
    from app.generator.matchday import ScheduledMatch
    from app.live.service import MatchdayService

STEP_MS = 1_000
CUT_COUNTDOWN_MS = 5_000
GOAL_COUNTDOWN_MS = 3_000
MIN_DWELL_MS = 75_000  # on a match at least this long before an automatic cut away
AFTER_GOAL_MS = 60_000  # after a goal on air, stay for the aftermath
AFTER_FULL_TIME_MS = 45_000  # after the final whistle on air, stay for the reaction
CUT_MARGIN = 0.2  # another match must score this much higher to take the screen...
STALE_MS = 240_000  # ...a margin that shrinks to nothing over four quiet minutes on one match
UNSEEN_BONUS_PER_MIN = 0.02  # a quiet spell checks in on the match not seen for longest
UNSEEN_BONUS_MAX = 0.2
MIN_SCORE = 0.2  # below this nothing is worth cutting to
HOLD_LIMIT_MS = 120_000  # a hold releases itself, so the channel never stays frozen
RESET_GAP_MS = 15_000  # nobody watched for this long: the channel starts afresh
HISTORY = 20

PRESSURE_WINDOW_MS = 180_000
PRESSURE_TAU_MS = 45_000  # recent threat counts most: e^-1 after 45 s
PRESSURE_SCALE = 0.15  # raw threat at which pressure reaches 63% (the busiest 10% of spells)
SHOT_WEIGHT = 3.0
STAKE_BASE = 0.15  # a match with nothing at stake still deserves the screen when it's wild
MAX_STAKE = 1.5


@dataclass
class _State:
    clock_ms: int
    on_air: Cut
    version: int = 0
    pending: PendingCut | None = None
    held_since: int | None = None
    pinned: str | None = None
    history: list[Cut] = field(default_factory=list)


class ChannelDirector:
    def __init__(self, service: "MatchdayService") -> None:
        self.service = service
        self.lock = threading.Lock()
        self.state: _State | None = None
        self.clocks = {
            m.match_id: [e.match_clock_ms for e in m.result.events] for m in service.matches
        }
        # Every goal of the day, in time order, for "a goal anywhere is an immediate cut".
        self.goals = sorted(
            (
                (e.match_clock_ms, m.match_id, e)
                for m in service.matches
                for e in m.result.events
                if e.type == "goal"
            ),
            key=lambda g: g[0],
        )
        self.goal_clocks = [clock for clock, _, _ in self.goals]

    # --- Driving the channel -----------------------------------------------------------------

    def sync(self, clock_ms: int) -> None:
        with self.lock:
            s = self.state
            if s is None or clock_ms < s.clock_ms or clock_ms - s.clock_ms > RESET_GAP_MS:
                self._start(clock_ms)
                return
            t = s.clock_ms - s.clock_ms % STEP_MS + STEP_MS
            while t <= clock_ms:
                self._tick(t)
                t += STEP_MS
            s.clock_ms = clock_ms

    def snapshot(self, clock_ms: int) -> Channel:
        self.sync(clock_ms)
        with self.lock:
            s = self.state
            assert s
            return Channel(
                clock_ms=s.clock_ms,
                version=s.version,
                on_air=s.on_air,
                pending=s.pending,
                held=s.held_since is not None,
                pinned_match_id=s.pinned,
                history=s.history,
                signals=sorted(self.signals(s.clock_ms), key=lambda x: -x.score),
            )

    # --- The producer ------------------------------------------------------------------------

    def take(self, clock_ms: int, match_id: str | None = None) -> None:
        """Take the pending cut now, or cut straight to `match_id`."""
        self.sync(clock_ms)
        with self.lock:
            s = self.state
            assert s
            if match_id is None:
                if s.pending:
                    self._take(s.pending.match_id, s.pending.reason, "producer", s.pending.package)
                return
            if match_id not in self.service.by_id:
                raise KeyError(match_id)
            if match_id != s.on_air.match_id:
                self._take(match_id, "manual", "producer", self._package(match_id, "manual"))

    def hold(self, clock_ms: int, held: bool) -> None:
        """Pause (or resume) automatic cuts. A pending cut is dropped."""
        self.sync(clock_ms)
        with self.lock:
            s = self.state
            assert s
            s.held_since = s.clock_ms if held else None
            if held:
                s.pending = None
            s.version += 1

    def pin(self, clock_ms: int, match_id: str | None) -> None:
        """Fix the feed on a match (cutting to it), or release it."""
        self.sync(clock_ms)
        with self.lock:
            s = self.state
            assert s
            if match_id is not None and match_id not in self.service.by_id:
                raise KeyError(match_id)
            s.pinned = match_id
            s.pending = None
            if match_id and match_id != s.on_air.match_id:
                self._take(match_id, "manual", "producer", self._package(match_id, "manual"))
            s.version += 1

    # --- The Director ------------------------------------------------------------------------

    def _start(self, clock_ms: int) -> None:
        """A fresh channel: on the most deserving match now (the featured one at kickoff)."""
        best = max(self.signals(clock_ms), key=lambda x: x.score, default=None)
        featured = next(m.match_id for m in self.service.matches if m.featured)
        match_id = best.match_id if best and best.score >= MIN_SCORE else featured
        version = self.state.version + 1 if self.state else 0
        cut = self._cut(clock_ms, match_id, "kickoff", "code", self._package(match_id, "kickoff"))
        self.state = _State(clock_ms=clock_ms, on_air=cut, version=version)

    def _tick(self, t: int) -> None:
        s = self.state
        assert s
        s.clock_ms = t
        if s.held_since is not None and t - s.held_since >= HOLD_LIMIT_MS:
            s.held_since = None
            s.version += 1
        if s.pending and t >= s.pending.take_at_ms:
            p = s.pending
            self._take(p.match_id, p.reason, "code", p.package)
            return
        automatic = s.held_since is None and s.pinned is None
        if not automatic:
            return
        on_air = self.service.by_id[s.on_air.match_id]
        last_goal = max(
            (
                c
                for c, match_id, _ in self.goals[: bisect_right(self.goal_clocks, t)]
                if match_id == on_air.match_id
            ),
            default=-AFTER_GOAL_MS,
        )
        full_time = on_air.result.full_time_ms
        # Staying for the aftermath: a goal on air, or the final whistle.
        aftermath = t - last_goal < AFTER_GOAL_MS or 0 <= t - full_time < AFTER_FULL_TIME_MS
        # A goal elsewhere: cut to it now, unless we're in an aftermath and it changes nothing.
        first = bisect_right(self.goal_clocks, t - STEP_MS)
        for _, match_id, goal in self.goals[first : bisect_right(self.goal_clocks, t)]:
            already = s.pending is not None and s.pending.reason == "goal"  # first goal wins
            swing = any(x.event_id == goal.event_id for x in self.service.swings)
            if match_id != on_air.match_id and not already and (swing or not aftermath):
                self._propose(match_id, "goal", t, GOAL_COUNTDOWN_MS, goal)
        if s.pending or aftermath or t - s.on_air.clock_ms < MIN_DWELL_MS or t % 5_000:
            return  # weigh the matches every five seconds once settled
        signals = {x.match_id: x for x in self.signals(t)}
        current = signals.get(s.on_air.match_id)
        best = max(
            (x for x in signals.values() if x.match_id != s.on_air.match_id),
            key=lambda x: x.score,
            default=None,
        )
        current_score = current.score if current else 0.0
        settled = t - s.on_air.clock_ms - MIN_DWELL_MS
        margin = CUT_MARGIN * max(0.0, 1 - settled / STALE_MS)
        if best and best.score >= MIN_SCORE and best.score > current_score + margin:
            self._propose(best.match_id, "pressure", t, CUT_COUNTDOWN_MS)
        elif settled >= STALE_MS and current_score < MIN_SCORE:
            # Quiet everywhere: check in on the match we've seen least lately.
            seen = {c.match_id: c.clock_ms for c in reversed(s.history)}
            seen[s.on_air.match_id] = t

            def appeal(x: MatchSignal) -> float:
                unseen_min = (t - seen.get(x.match_id, 0)) / 60_000
                return x.score + min(UNSEEN_BONUS_MAX, unseen_min * UNSEEN_BONUS_PER_MIN)

            pick = max(
                (x for x in signals.values() if x.match_id != s.on_air.match_id),
                key=appeal,
                default=None,
            )
            if pick:
                self._propose(pick.match_id, "check_in", t, CUT_COUNTDOWN_MS)

    def _propose(
        self,
        match_id: str,
        reason: CutReason,
        t: int,
        countdown: int,
        goal: MatchEvent | None = None,
    ) -> None:
        s = self.state
        assert s
        s.pending = PendingCut(
            match_id=match_id,
            reason=reason,
            proposed_ms=t,
            take_at_ms=t + countdown,
            package=self._package(match_id, reason, t, goal),
        )
        s.version += 1

    def _take(
        self, match_id: str, reason: CutReason, decided_by: DecidedBy, package: CutPackage
    ) -> None:
        s = self.state
        assert s
        s.history = [s.on_air, *s.history][:HISTORY]
        s.on_air = self._cut(s.clock_ms, match_id, reason, decided_by, package)
        s.pending = None
        s.version += 1

    @staticmethod
    def _cut(
        t: int, match_id: str, reason: CutReason, decided_by: DecidedBy, package: CutPackage
    ) -> Cut:
        return Cut(
            cut_id=f"cut_{t}_{match_id}",
            match_id=match_id,
            clock_ms=t,
            reason=reason,
            decided_by=decided_by,
            package=package,
        )

    # --- Signals -----------------------------------------------------------------------------

    def signals(self, t: int) -> list[MatchSignal]:
        """Every match still being played, scored on pressure and stakes."""
        table = self._table(t)
        out = []
        for m in self.service.matches:
            if t >= m.result.full_time_ms:
                continue
            home, away = (
                self._side(m, club_id, t, table) for club_id in (m.home.club_id, m.away.club_id)
            )
            score = max(x.pressure * (STAKE_BASE + min(x.stake, MAX_STAKE)) for x in (home, away))
            out.append(
                MatchSignal(match_id=m.match_id, home=home, away=away, score=round(score, 3))
            )
        return out

    def _side(self, m: "ScheduledMatch", club_id: str, t: int, table: LeagueTable) -> SideSignal:
        stake = next(
            (x for x in table.stakes if x.match_id == m.match_id and x.scorer_club_id == club_id),
            None,
        )
        return SideSignal(
            club_id=club_id,
            pressure=round(self._pressure(m, club_id, t), 3),
            stake=stake.weight if stake else 0.0,
            stake_summary=stake.summary if stake else None,
        )

    def _pressure(self, m: "ScheduledMatch", club_id: str, t: int) -> float:
        impacts = self.service.impacts[m.match_id]
        clocks = self.clocks[m.match_id]
        raw = 0.0
        for e in m.result.events[
            bisect_left(clocks, t - PRESSURE_WINDOW_MS) : bisect_right(clocks, t)
        ]:
            if e.team_id != club_id or e.type not in ("pass", "shot"):
                continue
            threat = max(impacts[e.event_id].threat, 0.0)
            weight = SHOT_WEIGHT if e.type == "shot" else 1.0
            raw += threat * weight * math.exp(-(t - e.match_clock_ms) / PRESSURE_TAU_MS)
        return 1 - math.exp(-raw / PRESSURE_SCALE)

    def _table(self, t: int) -> LeagueTable:
        return self.service._table(t // 1000)

    # --- Packages (written by code; the agents rewrite them when connected) ------------------

    def _package(
        self,
        match_id: str,
        reason: CutReason,
        t: int | None = None,
        goal: MatchEvent | None = None,
    ) -> CutPackage:
        service = self.service
        m = service.by_id[match_id]
        t = t if t is not None else (self.state.clock_ms if self.state else 0)
        at = min(t, m.result.full_time_ms)
        fixture = f"{m.home.name} v {m.away.name}"
        claims: list[Claim] = []

        goals = [e for e in m.result.events if e.type == "goal" and e.match_clock_ms <= at]
        home, away = m.result.score_at(at)
        story = f"{m.home.name} {home}-{away} {m.away.name}, {_minute(at)}."
        if goals:
            scorers = ", ".join(
                f"{service.surname(e.player_id)} {_minute(e.match_clock_ms)}" for e in goals
            )
            story += f" Goals: {scorers}."
            claims += [
                Claim(
                    text=f"Goal by {service.surname(e.player_id)} at {_minute(e.match_clock_ms)}",
                    evidence_event_ids=[e.event_id],
                )
                for e in goals
            ]

        table = self._table(at)
        at_stake = None
        if reason == "goal" and goal:
            scorer = service.surname(goal.player_id)
            club = service.club(goal.team_id).name
            why = f"Goal at {fixture}: {scorer} scores for {club} ({_minute(goal.match_clock_ms)})."
            swing = next((x for x in table.swings if x.event_id == goal.event_id), None)
            if swing:
                at_stake = f"As it stands: {swing.summary}"
            else:  # it changed nothing in the table yet: say what's still to play for
                stake = max(
                    (x for x in table.stakes if x.match_id == match_id),
                    key=lambda x: x.weight,
                    default=None,
                )
                if stake:
                    club = service.club(stake.scorer_club_id).name
                    at_stake = f"Still to play for: a goal for {club}: {stake.summary}"
        else:
            signal = next((x for x in self.signals(at) if x.match_id == match_id), None)
            # The side that earned the cut: pressure where it matters.
            side = (
                max((signal.home, signal.away), key=lambda x: x.pressure * (STAKE_BASE + x.stake))
                if signal
                else None
            )
            if reason == "pressure" and side:
                club = service.club(side.club_id).name
                shots = [
                    e
                    for e in m.result.events
                    if e.type == "shot"
                    and e.team_id == side.club_id
                    and at - PRESSURE_WINDOW_MS <= e.match_clock_ms <= at
                ]
                if shots:
                    count = "a shot" if len(shots) == 1 else f"{len(shots)} shots"
                    why = f"{club} are pressing: {count} in the last three minutes."
                    claims.append(
                        Claim(
                            text=f"{count.capitalize()} by {club} in the last three minutes",
                            evidence_event_ids=[e.event_id for e in shots],
                        )
                    )
                else:
                    why = f"{club} are pushing into the final third."
            elif reason == "check_in":
                why = f"Checking in at {fixture}."
            elif reason == "kickoff":
                why = f"The final day, live from {fixture}."
            else:
                why = f"The producer's call: {fixture}."
            if signal and side:
                staked = (
                    side
                    if side.stake_summary
                    else max((signal.home, signal.away), key=lambda x: x.stake)
                )
                if staked.stake_summary:
                    club = service.club(staked.club_id).name
                    at_stake = f"A goal for {club}: {staked.stake_summary}"
        return CutPackage(
            why=why, at_stake=at_stake, story=story, claims=claims, written_by=["code"]
        )


def _minute(clock_ms: int) -> str:
    return f"{clock_ms // 60_000 + 1}'"
