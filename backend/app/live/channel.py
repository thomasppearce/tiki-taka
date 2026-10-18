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
cited events. When the agents are connected (app/agents/channel_runner.py), a Watcher per match
keeps its story so far, and the Director agent chooses between the code's top candidates during
the countdown and writes the package; whatever they don't deliver in time, the code's stands.

Like the proposal desk, the channel only advances when someone asks for it (the channel stream
or an API call), one second at a time, so its decisions don't depend on how often it is polled.

A signed-in fan's own whip-around is another Director with a lens (app/live/lens.py) that weighs
what matters to their club or their fantasy XI. It shares the channel's Watcher stories, keeps
the channel (and so the Watchers) running while the fan watches, and calls no agents itself.
"""

import re
import threading
from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, cast

from app.agents.channel_brief import MatchBrief, match_brief
from app.detmath import exp
from app.live.lens import ChannelLens, Lens
from app.models import Claim, MatchEvent
from app.models.channel import (
    Channel,
    ChannelLog,
    Cut,
    CutPackage,
    CutReason,
    DecidedBy,
    LogAgent,
    MatchSignal,
    PendingCut,
    SideSignal,
)
from app.models.table import LeagueTable, Stake

if TYPE_CHECKING:
    from app.agents.schemas import CutDecision, DraftClaim, StoryUpdate
    from app.generator.matchday import ScheduledMatch
    from app.live.service import MatchdayService

STEP_MS = 1_000
CUT_COUNTDOWN_MS = 5_000
GOAL_COUNTDOWN_MS = 3_000
PENALTY_COUNTDOWN_MS = 10_000  # after a goal on air: its replay first, the penalty is 30 s off
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
REPLAY_CHANCE_MS = 90_000  # a pressure cut replays a big chance from the last 90 s...
REPLAY_CHANCE_XG = 0.08  # ...if there was one this good
STAKE_BASE = 0.15  # a match with nothing at stake still deserves the screen when it's wild
MAX_STAKE = 1.5

DEAD_BALL_MS = 10_000  # a match whose ball has been dead this long...
DEAD_BALL_DISCOUNT = 0.3  # ...holds the screen less firmly
RESTARTS = ("throw_in", "free_kick", "corner", "goal_kick")
CANDIDATES = 3  # the Director agent chooses between the code's top three
LATE_DECISION_MS = 15_000  # a decision after the cut can still rewrite its package this long
STORY_EVERY_MS = 15 * 60_000  # each Watcher retells its match at least this often...
STORY_GAP_MS = 60_000  # ...and at most once a minute, unless there's a goal
STORY_CHANCE_XG = 0.25  # a chance this big is worth a new story
LOG = 50


class ChannelAgents(Protocol):
    """The Watcher and Director agents (app/agents/channel_runner.py). Never blocks."""

    def request_story(
        self, channel: "ChannelDirector", match_id: str, key: str, brief: MatchBrief
    ) -> None: ...

    def request_decision(
        self,
        channel: "ChannelDirector",
        key: str,
        reason: str,
        on_air: str,
        briefs: Sequence[MatchBrief],
    ) -> None: ...


@dataclass
class _Story:
    text: str
    claims: list[Claim]
    as_of_ms: int


@dataclass
class _Decision:
    key: str
    reason: CutReason
    candidates: list[str]
    by_director: bool = False
    aired_ms: int = 0  # when its cut went on air (or the goal on air it is for)
    goal_on_air: bool = False


@dataclass
class _State:
    clock_ms: int
    on_air: Cut
    version: int = 0
    pending: PendingCut | None = None
    held_since: int | None = None
    pinned: str | None = None
    history: list[Cut] = field(default_factory=list)
    decision: _Decision | None = None  # the Director agent's say on the pending cut
    aired_decision: _Decision | None = None  # ...and on the cut on air, for late answers


class ChannelDirector:
    def __init__(
        self,
        service: "MatchdayService",
        lens: Lens | None = None,
        shared: "ChannelDirector | None" = None,
    ) -> None:
        self.service = service
        self.lens: Lens = lens or ChannelLens(service)
        self.shared = shared  # a fan's whip-around reads the channel's Watcher stories
        self.followed: dict[str, _Story] = {}  # ...and the one its packages last used, per match
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
        # Every penalty awarded, for "the channel goes to a penalty".
        self.penalties = sorted(
            (
                (e.match_clock_ms, m.match_id, e)
                for m in service.matches
                for e in m.result.events
                if e.type == "penalty"
            ),
            key=lambda g: g[0],
        )
        self.penalty_clocks = [clock for clock, _, _ in self.penalties]
        self.agents: ChannelAgents | None = None
        self.stories: dict[str, _Story] = {}  # each match's latest Watcher story
        self.story_asked: dict[str, int] = {}
        self.story_keys: dict[str, str] = {}  # each match's latest request: older answers are stale
        self.log: list[ChannelLog] = []
        # Versions keep counting through a reset, so a page holding the old channel knows the
        # new one is newer even when the clock jumped forward.
        self.last_version = -1

    # --- Driving the channel -----------------------------------------------------------------

    def sync(self, clock_ms: int) -> None:
        if self.shared:  # the Watchers work while anyone watches any whip-around
            self.shared.sync(clock_ms)
        with self.lock:
            s = self.state
            if s is not None and clock_ms < s.clock_ms:  # the matchday started over
                self.stories, self.story_asked, self.story_keys, self.log = {}, {}, {}, []
            if s is None or clock_ms < s.clock_ms or clock_ms - s.clock_ms > RESET_GAP_MS:
                # From the top of the minute: anyone joining in the same minute gets the same
                # channel (and the agents' cached answers for it), since every cut follows.
                self._start(clock_ms - clock_ms % 60_000)
                s = self.state
                assert s
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
                log=self.log,
                agents=(self.shared or self).agents is not None,
                lens=self.lens.info(s.clock_ms),
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
                    p = s.pending
                    self._log(
                        "producer", p.match_id, f"Took the cut to {self._fixture(p.match_id)} early"
                    )
                    self._take(p.match_id, p.reason, "producer", p.package, p.replay_event_id)
                return
            if match_id not in self.service.by_id:
                raise KeyError(match_id)
            if match_id != s.on_air.match_id:
                self._log("producer", match_id, f"Cut to {self._fixture(match_id)}")
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
            self._log("producer", None, "Held automatic cuts" if held else "Resumed automatic cuts")
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
            self._log(
                "producer",
                match_id,
                f"Pinned the feed on {self._fixture(match_id)}" if match_id else "Released the pin",
            )
            if match_id and match_id != s.on_air.match_id:
                self._take(match_id, "manual", "producer", self._package(match_id, "manual"))
            s.version += 1

    # --- The Director ------------------------------------------------------------------------

    def _start(self, clock_ms: int) -> None:
        """A fresh channel: on the most deserving match now (the featured one at kickoff)."""
        best = max(self.signals(clock_ms), key=lambda x: x.score, default=None)
        featured = next(m.match_id for m in self.service.matches if m.featured)
        match_id = best.match_id if best and best.score >= MIN_SCORE else featured
        version = (self.state.version if self.state else self.last_version) + 1
        package = self._package(match_id, "kickoff", clock_ms)
        cut = self._cut(clock_ms, match_id, "kickoff", "code", package)
        self.state = _State(clock_ms=clock_ms, on_air=cut, version=version)
        for m in self.service.matches:  # every Watcher tells its story from here
            if clock_ms < m.result.full_time_ms and m.match_id not in self.stories:
                self._ask_story(m.match_id, f"{m.match_id}:join{clock_ms // 60_000}", clock_ms)

    def _tick(self, t: int) -> None:
        s = self.state
        assert s
        s.clock_ms = t
        if s.on_air.also_until_ms is not None and t >= s.on_air.also_until_ms:
            s.on_air = s.on_air.model_copy(
                update={"also_match_id": None, "also_why": None, "also_until_ms": None}
            )
            s.version += 1
        if s.held_since is not None and t - s.held_since >= HOLD_LIMIT_MS:
            s.held_since = None
            s.version += 1
        self._watch(t)
        if self.shared:
            self._follow_stories()
        first = bisect_right(self.goal_clocks, t - STEP_MS)
        new_goals = self.goals[first : bisect_right(self.goal_clocks, t)]
        for _, match_id, goal in new_goals:
            if match_id == s.on_air.match_id:
                self._goal_on_air(goal, t)
        if s.pending and t >= s.pending.take_at_ms:
            p = s.pending
            by = "director" if s.decision and s.decision.by_director else "code"
            self._take(p.match_id, p.reason, by, p.package, p.replay_event_id)
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
        # A goal elsewhere: cut to it now if it matters to this whip-around, unless we're in an
        # aftermath and it matters only a little (to the channel: it changes nothing).
        for _, match_id, goal in new_goals:
            already = s.pending is not None and s.pending.reason == "goal"  # first goal wins
            weight = self.lens.goal_weight(match_id, goal)
            if (
                match_id != on_air.match_id
                and not already
                and (weight >= 1 or (weight > 0 and not aftermath))
            ):
                self._propose(match_id, "goal", t, GOAL_COUNTDOWN_MS, goal)
        # A penalty elsewhere: the ground holds its breath, and the channel goes there, if a
        # goal from it would matter to this whip-around. The kick is half a minute away, so
        # after a goal on air there's time to let its replay finish first.
        first = bisect_right(self.penalty_clocks, t - STEP_MS)
        for _, match_id, award in self.penalties[first : bisect_right(self.penalty_clocks, t)]:
            busy = s.pending is not None and s.pending.reason in ("goal", "penalty")
            if match_id == on_air.match_id or busy:
                continue
            m = self.service.by_id[match_id]
            stake, _ = self.lens.stake(m, award.team_id or "", t, self._table(t))
            if self.lens.kind == "channel" or stake > 0:
                countdown = PENALTY_COUNTDOWN_MS if aftermath else GOAL_COUNTDOWN_MS
                self._propose(match_id, "penalty", t, countdown, award)
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
        dead = self._dead_since(s.on_air.match_id, t)
        if dead is not None and t - dead >= DEAD_BALL_MS:
            # A free kick being set up, a substitution: in a whip-around that's the moment to
            # see what's happening elsewhere.
            current_score *= DEAD_BALL_DISCOUNT
        settled = t - s.on_air.clock_ms - MIN_DWELL_MS
        margin = CUT_MARGIN * max(0.0, 1 - settled / STALE_MS)
        others = sorted(
            (x for x in signals.values() if x.match_id != s.on_air.match_id),
            key=lambda x: -x.score,
        )
        if best and best.score >= MIN_SCORE and best.score > current_score + margin:
            self._propose(
                best.match_id,
                "pressure",
                t,
                CUT_COUNTDOWN_MS,
                candidates=[x.match_id for x in others[:CANDIDATES]],
            )
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
                rest = [x.match_id for x in others if x.match_id != pick.match_id]
                candidates = [pick.match_id, *rest[: CANDIDATES - 1]]
                self._propose(pick.match_id, "check_in", t, CUT_COUNTDOWN_MS, candidates=candidates)

    def _propose(
        self,
        match_id: str,
        reason: CutReason,
        t: int,
        countdown: int,
        goal: MatchEvent | None = None,
        candidates: list[str] | None = None,
    ) -> None:
        s = self.state
        assert s
        s.pending = PendingCut(
            match_id=match_id,
            reason=reason,
            proposed_ms=t,
            take_at_ms=t + countdown,
            package=self._package(match_id, reason, t, goal),
            replay_event_id=(
                goal.event_id if goal and goal.type == "goal" else self._chance(match_id, t)
            ),
        )
        s.version += 1
        candidates = [match_id, *[c for c in (candidates or []) if c != match_id]]
        self._log("code", match_id, f"Proposed cutting to {self._fixture(match_id)} ({reason})")
        s.decision = None
        if self.agents:
            key = f"{t}:{reason}:{'-'.join(candidates)}"
            s.decision = _Decision(key, reason, candidates)
            briefs = [self._brief(c, t) for c in candidates]
            on_air = self._brief(s.on_air.match_id, t)
            minutes = (t - s.on_air.clock_ms) // 60_000
            line = f"{on_air.situation}, on air for {minutes} min"
            self.agents.request_decision(self, key, reason, line, briefs)

    def _take(
        self,
        match_id: str,
        reason: CutReason,
        decided_by: DecidedBy,
        package: CutPackage,
        replay_event_id: str | None = None,
    ) -> None:
        s = self.state
        assert s
        left = s.on_air.match_id
        s.history = [s.on_air, *s.history][:HISTORY]
        s.on_air = self._cut(s.clock_ms, match_id, reason, decided_by, package, replay_event_id)
        if reason in ("goal", "penalty") and left != match_id:
            why = self._still_on(left, s.clock_ms)
            if why:
                ends = self.service.by_id[left].result.full_time_ms + 15_000
                s.on_air = s.on_air.model_copy(
                    update={
                        "also_match_id": left,
                        "also_why": why,
                        "also_until_ms": min(s.clock_ms + SPLIT_MS, ends),
                    }
                )
        s.aired_decision = s.decision if s.pending and s.pending.match_id == match_id else None
        if s.aired_decision:
            s.aired_decision.aired_ms = s.clock_ms
        s.pending, s.decision = None, None
        if decided_by != "producer":
            self._log(
                "director" if decided_by == "director" else "code",
                match_id,
                f"Cut to {self._fixture(match_id)}",
            )
        s.version += 1

    @staticmethod
    def _cut(
        t: int,
        match_id: str,
        reason: CutReason,
        decided_by: DecidedBy,
        package: CutPackage,
        replay_event_id: str | None = None,
    ) -> Cut:
        return Cut(
            cut_id=f"cut_{t}_{match_id}",
            match_id=match_id,
            clock_ms=t,
            reason=reason,
            decided_by=decided_by,
            package=package,
            replay_event_id=replay_event_id,
        )

    def _still_on(self, match_id: str, t: int) -> str | None:
        """Why the match a goal cut leaves should stay on screen beside it, or None: it has just
        had a goal, it is late with a race on the line, or a side is pushing hard."""
        m = self.service.by_id[match_id]
        if t >= m.result.full_time_ms:
            return None
        clocks = self.clocks[match_id]
        recent = [
            e
            for e in m.result.events[
                bisect_left(clocks, t - SPLIT_JUST_SCORED_MS) : bisect_right(clocks, t)
            ]
            if e.type == "goal"
        ]
        if recent:
            goal = recent[-1]
            club = self.service.club(goal.team_id).name
            return f"{self.service.surname(goal.player_id)} has just scored for {club} there."
        if t >= SPLIT_LATE_MS:
            races = _races(x for x in self._table(t).stakes if x.match_id == match_id)
            if races:
                return f"{races} still on the line there."
        signal = next((x for x in self.signals(t) if x.match_id == match_id), None)
        if signal:
            side = max((signal.home, signal.away), key=lambda x: x.pressure)
            if side.pressure >= SPLIT_PRESSURE:
                return f"{self.service.club(side.club_id).name} are pushing hard there."
        return None

    def _chance(self, match_id: str, t: int) -> str | None:
        """The best chance in this match in the last 90 s, worth replaying as we cut in."""
        m = self.service.by_id[match_id]
        impacts = self.service.impacts[match_id]
        clocks = self.clocks[match_id]
        shots = [
            e
            for e in m.result.events[
                bisect_left(clocks, t - REPLAY_CHANCE_MS) : bisect_right(clocks, t)
            ]
            if e.type == "shot" and impacts[e.event_id].threat >= REPLAY_CHANCE_XG
        ]
        best = max(shots, key=lambda e: impacts[e.event_id].threat, default=None)
        return best.event_id if best else None

    def _goal_on_air(self, goal: MatchEvent, t: int) -> None:
        """A goal in the match on air: the package now says what it changed, in the code's words
        at once and the Director's when they come. Same cut, so no stinger and no second replay."""
        s = self.state
        assert s
        match_id = s.on_air.match_id
        package = self._package(match_id, "goal", t, goal)
        s.on_air = s.on_air.model_copy(update={"package": package})
        s.version += 1
        if self.agents:
            key = f"{t}:goal:{match_id}"
            s.aired_decision = _Decision(key, "goal", [match_id], aired_ms=t, goal_on_air=True)
            brief = self._brief(match_id, t)
            line = f"{brief.situation}, the goal is on air"
            self.agents.request_decision(self, key, "goal", line, [brief])

    # --- The agents ---------------------------------------------------------------------------

    def _watch(self, t: int) -> None:
        """Ask each Watcher for a new story when its match turns: a goal, a red card, a big
        chance, or a quarter of an hour since the last."""
        if not self.agents:
            return
        for m in self.service.matches:
            if t >= m.result.full_time_ms + STEP_MS:
                continue
            clocks = self.clocks[m.match_id]
            impacts = self.service.impacts[m.match_id]
            turns = [
                e
                for e in m.result.events[
                    bisect_right(clocks, t - STEP_MS) : bisect_right(clocks, t)
                ]
                if e.type == "goal"
                or (e.type == "card" and e.attributes.card_color == "red")
                or (e.type == "shot" and impacts[e.event_id].threat >= STORY_CHANCE_XG)
            ]
            last = self.story_asked.get(m.match_id, -STORY_EVERY_MS)
            goal = any(e.type == "goal" for e in turns)
            if turns and (goal or t - last >= STORY_GAP_MS):
                self._ask_story(m.match_id, f"{m.match_id}:{turns[-1].event_id}", t)
            elif t - last >= STORY_EVERY_MS:
                self._ask_story(m.match_id, f"{m.match_id}:m{t // 60_000}", t)

    def _ask_story(self, match_id: str, key: str, t: int) -> None:
        if not self.agents:
            return
        self.story_asked[match_id] = t
        self.story_keys[match_id] = key
        self.agents.request_story(self, match_id, key, self._brief(match_id, t))

    def _follow_stories(self) -> None:
        """A fan's whip-around takes up the Watchers' newer stories as the channel gets them."""
        s = self.state
        assert s
        for cut in (s.on_air, s.pending):
            told = self._told(cut.match_id) if cut else None
            if not cut or not told or told.text == cut.package.story:
                continue
            package = _restory(cut.package, self.followed.get(cut.match_id), told)
            if cut is s.on_air:
                s.on_air = s.on_air.model_copy(update={"package": package})
            elif s.pending:
                s.pending = s.pending.model_copy(update={"package": package})
            self.followed[cut.match_id] = told
            s.version += 1

    def _told(self, match_id: str) -> _Story | None:
        """The match's latest Watcher story (a fan's whip-around reads the channel's)."""
        return (self.shared or self).stories.get(match_id)

    def _brief(self, match_id: str, t: int) -> MatchBrief:
        story = self._told(match_id)
        return match_brief(self.service, match_id, t, story.text if story else None)

    def story_ready(
        self,
        match_id: str,
        key: str,
        update: "StoryUpdate",
        seconds: float,
        tokens: int,
        cached: bool,
        sent_back: Sequence[str] = (),
    ) -> None:
        """A Watcher's checked story: it becomes the match's story so far, on air too."""
        with self.lock:
            s = self.state
            # Asked before the clock jumped (or overtaken by a newer request): out of date.
            if s is None or self.story_keys.get(match_id) != key:
                return
            old = self.stories.get(match_id)
            story = _Story(update.story, _claims(update.claims), s.clock_ms)
            self.stories[match_id] = story
            note = f"{seconds:.1f} s, {tokens} tokens" + (", cached" if cached else "")
            self._log_sent_back("Watcher's story", match_id, sent_back)
            self._log("watcher", match_id, f"{update.story} ({note})")
            if s.on_air.match_id == match_id:
                package = _restory(s.on_air.package, old, story)
                s.on_air = s.on_air.model_copy(update={"package": package})
            if s.pending and s.pending.match_id == match_id:
                package = _restory(s.pending.package, old, story)
                s.pending = s.pending.model_copy(update={"package": package})
            s.version += 1

    def reset(self) -> None:
        """Start afresh at the next sync: the clock jumped (the producer's demo control)."""
        with self.lock:
            if self.state:
                self.last_version = self.state.version
            self.state = None
            self.stories, self.story_asked, self.story_keys, self.log = {}, {}, {}, []

    def agent_note(self, agent: str, match_id: str | None, detail: str) -> None:
        """A Watcher's or the Director's own report, such as a model call it had to retry."""
        if agent in ("watcher", "director"):
            with self.lock:
                self._log(cast("LogAgent", agent), match_id, detail)

    def story_failed(self, match_id: str, key: str, reason: str) -> None:
        with self.lock:
            agent: LogAgent = "checker" if reason.startswith("checker") else "watcher"
            self._log(agent, match_id, f"Story not updated ({reason}); the last one stands")

    def decision_ready(
        self,
        key: str,
        decision: "CutDecision",
        seconds: float,
        tokens: int,
        cached: bool,
        sent_back: Sequence[str] = (),
    ) -> None:
        """The Director agent's choice and words: in time, it decides the pending cut; a little
        late, it can still rewrite the package of the cut it was for."""
        with self.lock:
            s = self.state
            if s is None:
                return
            note = f"{seconds:.1f} s, {tokens} tokens" + (", cached" if cached else "")
            self._log_sent_back("Director's answer", decision.match_id, sent_back)
            d = s.decision
            if d and d.key == key and s.pending:
                chosen = decision.match_id
                if chosen != s.pending.match_id:
                    passed = self._fixture(s.pending.match_id)
                    t = s.pending.proposed_ms
                    s.pending = s.pending.model_copy(
                        update={
                            "match_id": chosen,
                            "package": self._package(chosen, d.reason, t),
                            "replay_event_id": self._chance(chosen, t),
                        }
                    )
                    choice = f"Chose {self._fixture(chosen)} over {passed}"
                else:
                    choice = f"Agreed: {self._fixture(chosen)}"
                package = self._worded(s.pending.package, decision, chosen)
                s.pending = s.pending.model_copy(update={"package": package})
                d.by_director = True
                self._log("director", chosen, f"{choice}. {decision.why} ({note})")
            elif (
                (aired := s.aired_decision)
                and aired.key == key
                and decision.match_id == s.on_air.match_id
                and s.clock_ms - aired.aired_ms <= LATE_DECISION_MS
            ):
                package = self._worded(s.on_air.package, decision, s.on_air.match_id)
                s.on_air = s.on_air.model_copy(update={"package": package})
                when = "for the goal" if aired.goal_on_air else "just after the cut"
                self._log(
                    "director",
                    s.on_air.match_id,
                    f"Rewrote the package {when}: {decision.why} ({note})",
                )
            else:
                self._log("director", decision.match_id, f"Answered too late to use ({note})")
            s.version += 1

    def decision_failed(self, key: str, reason: str) -> None:
        with self.lock:
            s = self.state
            agent: LogAgent = "checker" if reason.startswith("checker") else "director"
            self._log(agent, None, f"No decision ({reason}); the code's pick stands")
            if s:
                s.version += 1

    def _worded(self, package: CutPackage, decision: "CutDecision", match_id: str) -> CutPackage:
        """The package with the Director's words, keeping the Watcher's story."""
        story = self._told(match_id)
        claims = _claims(decision.claims) + (story.claims if story else [])
        return package.model_copy(
            update={
                "why": decision.why,
                "at_stake": _sentence(decision.at_stake) or package.at_stake,
                "claims": claims,
                "written_by": (
                    ["watcher", "director", "checker"] if story else ["director", "checker"]
                ),
            }
        )

    def _log_sent_back(self, what: str, match_id: str, problems: Sequence[str]) -> None:
        """The checker's first look, when it sent a draft back and the redraft passed."""
        if problems:
            more = f" (and {len(problems) - 1} more)" if len(problems) > 1 else ""
            self._log(
                "checker", match_id, f"Sent the {what} back: {self._readable(problems[0])}{more}"
            )

    def _readable(self, problem: str) -> str:
        """A checker's note as the crew log shows it: what was wrong, without the instruction
        to the model after it (which names fields like at_stake), and fixtures, not match ids."""
        diagnosis = problem.split("; ")[0].rstrip(".")
        return MATCH_ID.sub(lambda m: self._fixture(m.group(0)), diagnosis) + "."

    def _log(self, agent: LogAgent, match_id: str | None, detail: str) -> None:
        t = self.state.clock_ms if self.state else 0
        entry = ChannelLog(clock_ms=t, agent=agent, match_id=match_id, detail=detail)
        self.log = [entry, *self.log][:LOG]

    def _fixture(self, match_id: str | None) -> str:
        if not match_id:
            return ""
        m = self.service.by_id[match_id]
        return f"{m.home.name} v {m.away.name}"

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
        weight, summary = self.lens.stake(m, club_id, t, table)
        return SideSignal(
            club_id=club_id,
            pressure=round(self._pressure(m, club_id, t), 3),
            stake=round(weight, 3),
            stake_summary=summary,
        )

    def _dead_since(self, match_id: str, t: int) -> int | None:
        """When the ball went dead in this match (a restart awarded and not yet taken), or
        None while it is in play."""
        events = self.service.by_id[match_id].result.events
        i = bisect_right(self.clocks[match_id], t) - 1
        while i >= 0:
            e = events[i]
            if e.type in ("pass", "shot", "kickoff", "goal", "half_end"):
                return None
            if e.type in RESTARTS:
                return e.match_clock_ms
            i -= 1
        return None

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
            raw += threat * weight * exp(-(t - e.match_clock_ms) / PRESSURE_TAU_MS)
        return 1 - exp(-raw / PRESSURE_SCALE)

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
        scoreline = f"{m.home.name} {home}-{away} {m.away.name}, {_minute(at)}."
        story = scoreline
        told = self._told(match_id)
        if told and self.shared:
            self.followed[match_id] = told
        if told:  # the Watcher's story so far
            story = told.text
            claims += told.claims
        elif goals:
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

        # A goal's own table move must count even when the whistle follows within the second.
        scored = goal is not None and goal.type == "goal"
        table = self._table(max(at, goal.match_clock_ms + 999) if goal and scored else at)
        at_stake = None
        if reason == "penalty" and goal:
            club = service.club(goal.team_id).name
            why = f"Penalty to {club}: {service.surname(goal.player_id)} to take it."
            clock_ms = goal.match_clock_ms
            foul = next(
                (e for e in m.result.events if e.type == "foul" and e.match_clock_ms == clock_ms),
                None,
            )
            claims.append(
                Claim(
                    text=f"Penalty to {club}",
                    evidence_event_ids=[goal.event_id, *([foul.event_id] if foul else [])],
                )
            )
            stake = next(
                (
                    x
                    for x in table.stakes
                    if x.match_id == match_id and x.scorer_club_id == goal.team_id
                ),
                None,
            )
            if stake:
                at_stake = f"If it goes in: {stake.summary}"
        elif reason == "goal" and goal:
            scorer = service.surname(goal.player_id)
            club = service.club(goal.team_id).name
            why = f"{scorer} scores for {club} ({_minute(goal.match_clock_ms)})."
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
                    at_stake = f"Still to play for: {_if_scored(club, stake.summary)}"
        else:
            signal = next((x for x in self.signals(at) if x.match_id == match_id), None)
            # The side that earned the cut: pressure where it matters.
            side = (
                max((signal.home, signal.away), key=lambda x: x.pressure * (STAKE_BASE + x.stake))
                if signal
                else None
            )
            # Joining a day under way reads like a pressure cut when someone is pushing.
            over = t >= m.result.full_time_ms
            joining = (
                reason == "kickoff" and at >= 60_000 and not over and side and side.pressure >= 0.2
            )
            if (reason == "pressure" or joining) and side:
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
            elif reason == "kickoff" and at < 60_000:
                day = (
                    "The season's last matchday"
                    if self.service.last_matchday
                    else f"Matchday {self.service.matchday_number}"
                )
                why = f"{day} kicks off, and we start at {fixture}."
            elif over:  # nothing left on the line
                why = f"Full time: {m.home.name} {home}-{away} {m.away.name}."
            else:  # a check-in, the producer's call, or joining a day under way
                races = _races(x for x in table.stakes if x.match_id == match_id)
                why = f"{races} on the line here: {scoreline}" if races else scoreline
            if (
                side and not over
            ):  # what's at stake in the table; the lens says what it means to you
                general = {x.scorer_club_id: x for x in table.stakes if x.match_id == match_id}
                staked = general.get(side.club_id) or max(
                    general.values(), key=lambda x: x.weight, default=None
                )
                if staked:
                    club = service.club(staked.scorer_club_id).name
                    at_stake = _sentence(_if_scored(club, staked.summary))
        return CutPackage(
            why=why,
            at_stake=at_stake,
            story=story,
            claims=claims,
            written_by=["watcher"] if told else ["code"],
            for_you=self.lens.for_you(match_id, at),
            storyline=self._storyline(match_id, t, goal),
        )

    def _storyline(self, match_id: str, t: int, goal: MatchEvent | None) -> str | None:
        """The player story to lead with: a goal that moved the Golden Boot race says so; else
        the match's most important story."""
        if goal is not None and goal.type == "goal":
            swing = next((x for x in self.service.boot_swings if x.event_id == goal.event_id), None)
            if swing:
                return swing.summary
        stories = self.service.stories(match_id, t)
        return stories[0] if stories else None


def _minute(clock_ms: int) -> str:
    return f"{clock_ms // 60_000 + 1}'"


# A split screen (a broadcast double box): a goal cut away from a match that still matters keeps
# it on screen beside the goal for a minute; late with a race on the line, or just after a goal.
SPLIT_MS = 60_000
SPLIT_LATE_MS = 80 * 60_000
SPLIT_JUST_SCORED_MS = 60_000
SPLIT_PRESSURE = 0.5

MATCH_ID = re.compile(r"\bm_l\d+_\d+\b")
RACES = {"champions": "the title", "continental": "the top four", "relegation": "the drop"}


def _races(stakes: Iterable[Stake]) -> str | None:
    """The races a goal in this match would change, as the start of a sentence: "The title and
    the drop are" (the title race covers the top four)."""
    zones = {z for x in stakes for c in x.changes for z in (c.from_zone, c.to_zone) if z}
    if "champions" in zones:
        zones.discard("continental")
    names = [name for zone, name in RACES.items() if zone in zones]
    if not names:
        return None
    joined = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"
    return f"{joined[:1].upper()}{joined[1:]} {'is' if len(names) == 1 else 'are'}"


def _if_scored(club: str, summary: str) -> str:
    """What a goal for `club` would do, naming them once: "if Halvern Town score, they go top on
    goal difference; ..." (a stake's summary leads with the scorer when it moves them)."""
    if summary.startswith(f"{club} "):
        return f"if {club} score, they {summary[len(club) + 1:]}"
    return f"if {club} score, {summary}"


def _sentence(text: str | None) -> str | None:
    """An agent's line as a sentence: it may copy a brief line that starts lower case."""
    return text[:1].upper() + text[1:] if text else text


def _claims(claims: "Sequence[DraftClaim]") -> list[Claim]:
    return [
        Claim(text=c.text, evidence_event_ids=c.evidence_event_ids)
        for c in claims
        if c.evidence_event_ids
    ]


def _restory(package: CutPackage, old: _Story | None, new: _Story) -> CutPackage:
    """A package with a newer story so far (and its claims in place of the old story's)."""
    claims = [c for c in package.claims if not (old and c in old.claims)] + new.claims
    written = [w for w in package.written_by if w != "code"]
    written = ["watcher", *[w for w in written if w != "watcher"]]
    return package.model_copy(update={"story": new.text, "claims": claims, "written_by": written})
