"""Tick-based synthetic match engine.

The match is simulated in 0.2 s ticks, and each club plays to its tactical profile (tactics.py):
where its back line holds, when it presses, how wide it plays, how quickly and how directly it
moves the ball, and how often its forwards run in behind. Every tick:

- each team's shape moves as a unit: the back line steps up and drops together, the block shifts
  toward the ball, and the side in possession spreads out while two teammates offer short angles;
- forwards wait on the offside line, then make timed runs in behind, and the carrier looks to
  release them before they stray offside;
- players react to the play with a short lag, accelerate the way athletes do (hard from a
  standstill, gently near top speed), brake to arrive, and are never perfectly still;
- the carrier carries into space, and decides when to pass, shoot, or keep going.

The laws the engine enforces: offside (judged at the moment of the pass, level is onside, never
from a throw-in, goal kick, or corner), throw-ins, goal kicks, corners, and free kicks as dead
balls (no pressing or tackling until the restart is taken), and nobody tackles a keeper holding
the ball in their own box.

Events are emitted as they happen, so they always agree with the tracking data: the ball is where
the events say it is, and speeds, distance covered, and sprints come out of the movement rather
than being invented.

Coordinates are meters internally (105 x 68); events and frames use the normalized 0-100 pitch.
A side's "team frame" is the pitch as that side sees it, attacking toward x = 105.
"""

from __future__ import annotations

import math
import random
from array import array
from dataclasses import dataclass, field
from typing import Literal

from app.generator.storylines import Beat, Side, Storyline
from app.generator.tactics import Tactics
from app.generator.world import FORMATIONS, Club, Player, Role
from app.models import EventAttributes, MatchEvent, TrackingFrame
from app.models.common import PitchPoint
from app.models.events import EventType, Outcome
from app.models.tracking import PlayerPosition

TICK_MS = 200
DT = TICK_MS / 1000
FRAME_EVERY = 2  # record tracking every 2 ticks (2.5 Hz); frame_at interpolates smoothly
L, W = 105.0, 68.0
HALF_MS = 45 * 60_000
ACCEL_MAX = 7.0  # m/s^2 from a standstill, falling off toward top speed
ACCEL_FLOOR = 0.8  # m/s^2 still available at top speed, for changing direction
DECEL_MAX = 6.0  # m/s^2 of braking
SPRINT_MPS = 7.0  # 25.2 km/h, the usual high-intensity threshold
SPRINT_MIN_MS = 1_000
GOAL_PAUSE_MS = 65_000
HALF_TIME_WALK_MS = 45_000  # the half-time break is skipped; players walk to their kickoff spots
BALL_FETCH_MPS = 8.0  # during a stoppage the ball is fetched to the restart spot, never moved
RESTART_PATIENCE_MS = 20_000
MAX_ADDED_MS = 5 * 60_000  # how long a restart may wait for the taker before it is forced
OFFSIDE_TOLERANCE_M = 0.25  # level is onside; this is the smallest margin an assistant flags
HOLD_LINE_M = 0.8  # how far onside a forward waits before a run
APPROACH_GAIN = 0.45  # m/s of approach speed per meter still to cover: small moves are walks
DRIFT_M = 0.7  # how far players sway around their spot when the play is elsewhere
SUPPORT_BLEND = 0.6  # how strongly the two nearest teammates move to offer the carrier an angle
SETTLE_MS = 1_500  # a team reshapes for attack or defence once a possession has settled
OTHER: dict[Side, Side] = {"home": "away", "away": "home"}

Restart = Literal["kickoff", "throw", "goal_kick", "corner", "free_kick"]
NO_OFFSIDE_FROM: tuple[Restart, ...] = ("throw", "goal_kick", "corner")
# How long the ball is dead before each restart is taken (ms). With these, about a third of the
# match is stoppages, as in real football (the ball is in play for roughly 55-60 minutes).
STOPPAGE_MS: dict[Restart, tuple[int, int]] = {
    "throw": (10_000, 18_000),
    "goal_kick": (18_000, 28_000),
    "corner": (25_000, 35_000),
    "free_kick": (18_000, 32_000),
}
SUBSTITUTION_MS = (12_000, 20_000)  # added to the stoppage it is made in


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _seg_dist(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Distance from point p to segment a-b."""
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else _clamp(((px - ax) * dx + (py - ay) * dy) / length2, 0, 1)
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _ease(current: float, target: float, tau_s: float) -> float:
    """Move `current` toward `target` like a first-order lag with time constant `tau_s`."""
    return current + (target - current) * (1 - math.exp(-DT / tau_s))


def expected_goals(distance_m: float, angle_rad: float) -> float:
    """A simple location xG: falls off with distance and with how wide the shot is."""
    return _clamp(
        0.9 * math.exp(-distance_m / 8.0) * (0.35 + 0.65 * math.cos(angle_rad)), 0.01, 0.8
    )


def _back_line(formation: str) -> float:
    """Where the formation's defenders stand, on average: the reference for its shape."""
    xs = [sx for role, sx, _ in FORMATIONS[formation] if role == "def"]
    return sum(xs) / len(xs)


@dataclass(eq=False)
class _PlayerState:
    player: Player
    side: Side
    slot: int  # 0-10, formation slot
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    tx: float = 0.0  # where the player is heading: their target, seen with a reaction lag
    ty: float = 0.0
    lag_s: float = 0.4
    sway: tuple[float, float, float, float] = (12.0, 0.0, 15.0, 0.0)  # periods (s) and phases
    distance: float = 0.0
    on_pitch: bool = True
    yellows: int = 0
    sprint_ms: int = 0
    sprint_from: tuple[float, float] = (0.0, 0.0)
    sprint_top: float = 0.0
    sprint_len: float = 0.0
    last_pressure_ms: int = -60_000
    run_until_ms: int = 0  # a run in behind is on until then
    run_burst_ms: int = 0  # before this, the runner shapes the run along the line
    run_to: tuple[float, float] = (0.0, 0.0)
    run_effort: float = 1.0
    next_run_ms: int = 0
    transition_effort: float = 0.7  # how hard they run in this transition (redrawn each turnover)

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    def running(self, t: int) -> bool:
        return self.run_until_ms > t


@dataclass
class _Flight:
    """The ball in the air: from where to where, when it lands, and who ends up with it."""

    x0: float
    y0: float
    x1: float
    y1: float
    t0: int
    t1: int
    receiver: _PlayerState | None  # None: nobody collects it (out of play, or in the net)
    restart_side: Side | None = None  # who restarts if it goes out
    out_of_play: bool = True  # False for a goal: the kickoff is already arranged


@dataclass
class FrameStore:
    """Tracking frames at FRAME_EVERY ticks, plus who occupied each of the 22 slots when."""

    match_id: str
    data: array = field(default_factory=lambda: array("f"))  # per frame: bx, by, 22 x (x, y)
    occupants: list[list[tuple[int, str]]] = field(default_factory=list)  # per slot: (from_ms, id)
    teams: list[str] = field(default_factory=list)  # per slot: team_id

    FRAME_MS = TICK_MS * FRAME_EVERY
    STRIDE = 2 + 22 * 2

    @property
    def count(self) -> int:
        return len(self.data) // self.STRIDE

    def frame_at(self, clock_ms: float) -> TrackingFrame:
        """The frame at any instant. Players follow a Catmull-Rom curve through the recorded
        frames, so paths and speeds are smooth; the ball moves in straight lines, as it does."""
        k = _clamp(clock_ms / self.FRAME_MS, 0, self.count - 1)
        k1 = int(k)
        k2 = min(k1 + 1, self.count - 1)
        k0, k3 = max(k1 - 1, 0), min(k2 + 1, self.count - 1)
        f = k - k1
        offsets = [k0 * self.STRIDE, k1 * self.STRIDE, k2 * self.STRIDE, k3 * self.STRIDE]
        d = self.data
        frame_s = self.FRAME_MS / 1000
        players = []
        for slot in range(22):
            i = 2 + slot * 2
            xs = [d[o + i] for o in offsets]
            ys = [d[o + i + 1] for o in offsets]
            if math.isnan(xs[1]) or math.isnan(xs[2]):
                continue  # sent off
            if math.isnan(xs[0]) or math.isnan(xs[3]):
                xs[0], ys[0], xs[3], ys[3] = xs[1], ys[1], xs[2], ys[2]
            x, dx = _catmull_rom(xs, f)
            y, dy = _catmull_rom(ys, f)
            players.append(
                PlayerPosition(
                    player_id=self._occupant(slot, clock_ms),
                    team_id=self.teams[slot],
                    x=round(_clamp(x, 0, L) / L * 100, 2),
                    y=round(_clamp(y, 0, W) / W * 100, 2),
                    speed_kmh=round(math.hypot(dx, dy) / frame_s * 3.6, 1),
                )
            )
        a, b = offsets[1], offsets[2]
        ball = PitchPoint(
            x=round(_clamp(d[a] + (d[b] - d[a]) * f, 0, L) / L * 100, 2),
            y=round(_clamp(d[a + 1] + (d[b + 1] - d[a + 1]) * f, 0, W) / W * 100, 2),
        )
        return TrackingFrame(
            match_id=self.match_id, match_clock_ms=int(clock_ms), ball=ball, players=players
        )

    def _occupant(self, slot: int, clock_ms: float) -> str:
        current = self.occupants[slot][0][1]
        for since, player_id in self.occupants[slot]:
            if since <= clock_ms:
                current = player_id
        return current


def _exit_point(ax: float, ay: float, bx: float, by: float) -> tuple[float, float]:
    """Where a ball travelling from a through b leaves the pitch."""
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy) or 1.0
    dx, dy = dx / length, dy / length
    steps = [
        (edge - start) / d
        for start, d, edges in ((bx, dx, (0.0, L)), (by, dy, (0.0, W)))
        if abs(d) > 1e-6
        for edge in edges
        if (edge - start) / d > 0
    ]
    s = min(steps, default=0.0)
    return _clamp(bx + dx * s, 0.0, L), _clamp(by + dy * s, 0.0, W)


def _catmull_rom(p: list[float], f: float) -> tuple[float, float]:
    """Value and derivative (per frame) at f in [0, 1] between p[1] and p[2]."""
    a = 2 * p[1]
    b = p[2] - p[0]
    c = 2 * p[0] - 5 * p[1] + 4 * p[2] - p[3]
    d = -p[0] + 3 * p[1] - 3 * p[2] + p[3]
    return 0.5 * (a + b * f + c * f * f + d * f**3), 0.5 * (b + 2 * c * f + 3 * d * f * f)


@dataclass
class MatchResult:
    match_id: str
    home: Club
    away: Club
    storyline: Storyline
    events: list[MatchEvent]
    frames: FrameStore
    full_time_ms: int

    def score_at(self, clock_ms: float) -> tuple[int, int]:
        home = away = 0
        for e in self.events:
            if e.match_clock_ms > clock_ms:
                break
            if e.type == "goal":
                if e.team_id == self.home.club_id:
                    home += 1
                else:
                    away += 1
        return home, away


class MatchEngine:
    """Simulates one match. Same clubs, storyline, and seed give the same match."""

    def __init__(self, match_id: str, home: Club, away: Club, storyline: Storyline, seed: int):
        self.match_id = match_id
        self.clubs: dict[Side, Club] = {"home": home, "away": away}
        self.story = storyline
        self.rng = random.Random(seed)
        self.t = 0
        self.events: list[MatchEvent] = []
        self.n = 0
        self.frames = FrameStore(match_id)
        self.players: list[_PlayerState] = []
        self.bench: dict[Side, list[Player]] = {}
        for side in ("home", "away"):
            club = self.clubs[side]
            for slot, player in enumerate(club.squad[:11]):
                x, y = self._kickoff_spot(side, slot, kicking=False)
                state = _PlayerState(player, side, slot, x, y, tx=x, ty=y)
                self._settle(state)
                self.players.append(state)
                self.frames.occupants.append([(0, player.player_id)])
                self.frames.teams.append(club.club_id)
            self.bench[side] = list(club.squad[11:])
        self.line: dict[Side, float] = {
            side: _back_line(self.clubs[side].formation) for side in ("home", "away")
        }
        self.holder: _PlayerState | None = None
        self.flight: _Flight | None = None
        self.ball = (L / 2, W / 2)
        self.possession: Side = "home"
        self.possession_since = 0
        self.shape_owner: Side = "home"  # the side whose shape is set up to attack
        self.next_action_ms = 0
        self.carry_from = (L / 2, W / 2)
        self.press_on = True  # whether the defending side presses this possession
        self.dead_until_ms = 0
        self.restart: tuple[Side, Restart] | None = None  # who takes the next restart, and what
        self.restart_taker: _PlayerState | None = None
        self.restart_spot: tuple[float, float] | None = None  # where the ball is being fetched to
        self.offside_applies = True  # False for the first pass from a throw-in, goal kick, corner
        self.offsides: dict[Side, int] = {"home": 0, "away": 0}  # a side learns from each flag
        self.pending_beats: list[Beat] = sorted(storyline.beats, key=lambda b: b.minute)
        self.subs_due: dict[Side, list[int]] = {
            side: sorted(self.rng.randint(58 * 60_000, 82 * 60_000) for _ in range(3))
            for side in ("home", "away")
        }
        self.full_time_ms = 90 * 60_000 + self.rng.randint(1, 5) * 60_000

    def _settle(self, p: _PlayerState) -> None:
        """A player's own rhythm: how quickly they react, and how they sway off the ball."""
        p.lag_s = 0.3 + 0.35 * (1 - p.player.work_rate) + self.rng.uniform(0, 0.12)
        p.sway = (
            self.rng.uniform(16, 32),
            self.rng.uniform(0, 2 * math.pi),
            self.rng.uniform(16, 32),
            self.rng.uniform(0, 2 * math.pi),
        )

    # --- Main loop ----------------------------------------------------------------------------

    def run(self) -> MatchResult:
        self._reset_positions("home")
        self._kickoff("home")
        second_half = False
        tick = 0
        # Added time: the referee plays on (up to five more minutes) while a scripted goal is due.
        while self.t < self.full_time_ms or (
            self.t < self.full_time_ms + MAX_ADDED_MS
            and any(b.kind == "goal" for b in self.pending_beats)
        ):
            if not second_half and self.t >= HALF_MS:
                self._emit("half_end", None, None, None)
                second_half = True
                self.flight = None
                self._stop_for_kickoff("away", HALF_TIME_WALK_MS)
            self._substitutions()
            self._update_ball()
            self._update_holder()
            self._update_runs()
            self._move_players()
            self._pressure_events()
            if tick % FRAME_EVERY == 0:
                self._record_frame()
            tick += 1
            self.t += TICK_MS
        self._emit("half_end", None, None, None)
        return MatchResult(
            self.match_id,
            self.clubs["home"],
            self.clubs["away"],
            self.story,
            self.events,
            self.frames,
            self.t,
        )

    # --- Geometry helpers -------------------------------------------------------------------

    @staticmethod
    def _to_team(side: Side, x: float, y: float) -> tuple[float, float]:
        return (x, y) if side == "home" else (L - x, W - y)

    _from_team = _to_team  # the mirror is its own inverse

    def _minute(self) -> float:
        return self.t / 60_000

    def _tactics(self, side: Side) -> Tactics:
        return self.clubs[side].tactics

    def _role(self, p: _PlayerState) -> Role:
        return FORMATIONS[self.clubs[p.side].formation][p.slot][0]

    def _advantage(self, side: Side) -> float:
        """How much the storyline favors `side` right now, in [-1, 1], plus active goal beats."""
        dominance = self.story.dominance_at(self._minute())
        advantage = dominance if side == "home" else -dominance
        if self._forcing(side, "goal"):
            advantage += 0.6
        return _clamp(advantage, -1, 1)

    def _forcing(self, side: Side, kind: str) -> Beat | None:
        for beat in self.pending_beats:
            if beat.side == side and beat.kind == kind and self._minute() >= beat.minute:
                return beat
        return None

    def _team(self, side: Side) -> list[_PlayerState]:
        return [p for p in self.players if p.side == side and p.on_pitch]

    def _offside_line(self, attacking: Side) -> float:
        """In the attacking side's frame: the second-last opponent or the ball, whichever is
        nearer the goal line, and never inside the attackers' own half."""
        xs = sorted(
            (self._to_team(attacking, o.x, o.y)[0] for o in self._team(OTHER[attacking])),
            reverse=True,
        )
        second_last = xs[1] if len(xs) > 1 else L
        ball_x = self._to_team(attacking, *self.ball)[0]
        return max(second_last, ball_x, L / 2)

    def _offside(self, p: _PlayerState, line: float) -> bool:
        return self._to_team(p.side, p.x, p.y)[0] > line + OFFSIDE_TOLERANCE_M

    def _kickoff_spot(self, side: Side, slot: int, kicking: bool) -> tuple[float, float]:
        club = self.clubs[side]
        _, sx, sy = FORMATIONS[club.formation][slot]
        x = min(sx * 0.62, 49.5)
        if kicking and slot == 9:
            x, sy = 51.5, 34.0  # the taker, just behind the ball
        elif kicking and slot == 10:
            x, sy = 50.0, 30.5
        return self._from_team(side, x, sy)

    # --- Restarts ---------------------------------------------------------------------------

    def _reset_positions(self, kicking: Side) -> None:
        """Line everyone up for the opening kickoff (the only time anyone is placed directly)."""
        for p in self.players:
            if p.on_pitch:
                p.x, p.y = self._kickoff_spot(p.side, p.slot, kicking=p.side == kicking)
                p.tx, p.ty = p.x, p.y
                p.vx = p.vy = 0.0
                p.run_until_ms = 0
        for side in ("home", "away"):
            self.line[side] = _back_line(self.clubs[side].formation)

    def _kickoff_taker(self, side: Side) -> _PlayerState:
        team = self._team(side)
        return next((p for p in team if p.slot >= 9), None) or team[-1]

    def _kickoff(self, side: Side) -> None:
        taker = self._kickoff_taker(side)
        self.ball = (L / 2, W / 2)
        self._give(taker, hold_ms=900)
        self._emit("kickoff", taker, side, self.ball, outcome="success")

    def _stop_for_kickoff(self, side: Side, pause_ms: int) -> None:
        """Stop play until `side` kicks off; everyone walks back to their kickoff spots."""
        self.holder = None
        self.possession = side
        self.shape_owner = side
        self.dead_until_ms = self.t + pause_ms
        self.restart = (side, "kickoff")
        self.restart_spot = (L / 2, W / 2)
        self.restart_taker = None
        for p in self.players:
            p.run_until_ms = 0

    def _set_restart(
        self, side: Side, kind: Restart, spot: tuple[float, float], dead_ms: int
    ) -> None:
        """Stop play: `side` takes a `kind` restart from `spot` once `dead_ms` has passed."""
        self.holder = None
        self.flight = None
        self.possession = side
        self.shape_owner = side  # a stoppage gives everyone time to reorganise
        self.restart_spot = spot
        self.dead_until_ms = self.t + dead_ms
        self.restart = (side, kind)
        team = self._team(side)
        keeper = next((p for p in team if p.slot == 0), None)
        if kind == "goal_kick" and keeper:
            self.restart_taker = keeper
        else:
            outfield = [p for p in team if p.slot != 0] or team
            self.restart_taker = min(
                outfield, key=lambda p: math.hypot(p.x - spot[0], p.y - spot[1])
            )
        for p in self.players:
            p.run_until_ms = 0

    def _stopped(self) -> bool:
        """The ball is dead: a restart is pending (or a stoppage is still running)."""
        return self.restart is not None or self.t < self.dead_until_ms

    def _stoppage(self, kind: Restart) -> int:
        low, high = STOPPAGE_MS[kind]
        return int(self.rng.uniform(low, high))

    def _give(self, player: _PlayerState, hold_ms: int | None = None) -> None:
        if self.possession != player.side:
            self.offside_applies = True
            self.possession_since = self.t
            for p in self.players:
                p.transition_effort = self.rng.uniform(0.6, 0.95) * (0.9 + 0.1 * p.player.work_rate)
            for p in self.players:
                p.run_until_ms = 0
        self.holder = player
        self.flight = None
        self.possession = player.side
        if hold_ms is None:
            pressure = self._pressure_on(player)
            tempo = self._tactics(player.side).tempo
            hold_ms = int(
                self.rng.uniform(1_000, 2_900) * (1 - 0.4 * pressure) * (1.25 - 0.5 * tempo)
            )
        self.next_action_ms = self.t + hold_ms
        self.carry_from = (player.x, player.y)
        # Whether the other side presses this possession: their intensity, and how they're doing.
        defending = OTHER[player.side]
        intensity = self._tactics(defending).press_intensity
        self.press_on = self.rng.random() < 0.2 + 0.6 * intensity + 0.15 * self._advantage(
            defending
        )

    # --- Ball -------------------------------------------------------------------------------

    def _update_ball(self) -> None:
        if self.flight:
            f = self.flight
            u = _clamp((self.t - f.t0) / max(1, f.t1 - f.t0), 0, 1)
            self.ball = (f.x0 + (f.x1 - f.x0) * u, f.y0 + (f.y1 - f.y0) * u)
            if self.t >= f.t1:
                r = f.receiver
                if (
                    r
                    and r.on_pitch
                    and math.hypot(r.x - f.x1, r.y - f.y1) > 2
                    and self.t < f.t1 + 3_000
                ):
                    return  # the ball has stopped; the receiver is still getting to it
                if r and r.on_pitch:
                    self._give(r)
                elif f.out_of_play:
                    self._out_of_play(f)
                else:
                    self.flight = None
        elif self.holder:
            direction = 1 if self.holder.side == "home" else -1  # home attacks toward x = L
            self.ball = (_clamp(self.holder.x + 0.6 * direction, 0, L), self.holder.y)
        elif self.restart_spot:  # fetched to where play restarts
            (bx, by), (sx, sy) = self.ball, self.restart_spot
            d = math.hypot(sx - bx, sy - by)
            step = BALL_FETCH_MPS * DT
            self.ball = (
                (sx, sy) if d <= step else (bx + (sx - bx) / d * step, by + (sy - by) / d * step)
            )

    def _out_of_play(self, f: _Flight) -> None:
        side = f.restart_side or OTHER[self.possession]
        if f.x1 <= 1.0 or f.x1 >= L - 1.0:  # over a goal line
            own_line = self._to_team(side, f.x1, f.y1)[0] < L / 2
            if own_line:
                spot = self._from_team(side, 5.5, 34 + self.rng.choice((-9.0, 9.0)))
                self._set_restart(side, "goal_kick", spot, self._stoppage("goal_kick"))
            else:
                corner_y = 0.5 if self._to_team(side, f.x1, f.y1)[1] < 34 else W - 0.5
                spot = self._from_team(side, L - 0.5, corner_y)
                self._set_restart(side, "corner", spot, self._stoppage("corner"))
        else:
            spot = (_clamp(f.x1, 1, L - 1), 0.3 if f.y1 < W / 2 else W - 0.3)
            self._set_restart(side, "throw", spot, self._stoppage("throw"))

    def _update_holder(self) -> None:
        h = self.holder
        if not h or self.flight or self.t < self.dead_until_ms:
            if self.restart and self.t >= self.dead_until_ms:
                self._take_restart()
            return
        if self._try_tackle(h):
            return
        hx, _ = self._to_team(h.side, h.x, h.y)
        carried = math.hypot(h.x - self.carry_from[0], h.y - self.carry_from[1])
        if self.t >= self.next_action_ms or hx > L - 5 or carried > 14:
            self._decide(h)

    def _take_restart(self) -> None:
        """Take the pending restart once the ball and the taker are in place. Nobody is moved:
        if the taker is still on their way, play waits for them."""
        assert self.restart
        side, kind = self.restart
        spot = self.restart_spot or self.ball
        overdue = self.t - self.dead_until_ms > RESTART_PATIENCE_MS
        ready = math.hypot(self.ball[0] - spot[0], self.ball[1] - spot[1]) < 0.5
        if kind == "kickoff":
            taker = self._kickoff_taker(side)
            mark = self._kickoff_spot(side, taker.slot, kicking=True)
        else:
            if self.restart_taker is None or not self.restart_taker.on_pitch:
                self.restart_taker = min(
                    self._team(side), key=lambda q: math.hypot(q.x - spot[0], q.y - spot[1])
                )
            taker = self.restart_taker
            mark = spot
        ready = ready and math.hypot(taker.x - mark[0], taker.y - mark[1]) < 1.0
        if not (ready or overdue):
            return
        self.restart = None
        self.restart_spot = None
        self.restart_taker = None
        if kind == "kickoff":
            self._kickoff(side)
            return
        self.ball = spot
        self.offside_applies = kind not in NO_OFFSIDE_FROM
        self._give(taker, hold_ms=700 if kind in ("throw", "free_kick") else 1_000)

    # --- Decisions ----------------------------------------------------------------------------

    def _decide(self, h: _PlayerState) -> None:
        hx, hy = self._to_team(h.side, h.x, h.y)
        goal_d = math.hypot(L - hx, 34 - hy)
        angle = abs(math.atan2(hy - 34, L - hx))
        xg = expected_goals(goal_d, angle)
        forcing = self._forcing(h.side, "goal")
        shot_p = 0.0
        if goal_d < 30 and angle < 1.1:
            shot_p = _clamp(xg * 1.1, 0, 0.55) * (1 + 0.3 * self._advantage(h.side))
            if goal_d > 16 and angle < 0.7:
                shot_p += 0.07  # a strike from range when the space opens up
            # Defenders between the shooter and goal close the shooting lane.
            shot_p *= 0.7 ** self._defenders_in_cone(h)
            if forcing:  # a scripted goal is due: work it into the box, then finish it
                named = not forcing.player_number or forcing.player_number == h.player.number
                shot_p = (0.9 if named else 0.35) if goal_d < 26 else 0.0
        if self.rng.random() < shot_p:
            self._shoot(h, goal_d, angle, xg)
            return
        if self._pass(h):
            return
        self.next_action_ms = self.t + int(self.rng.uniform(400, 900))  # keep the ball

    def _pass(self, h: _PlayerState) -> bool:
        side = h.side
        tactics = self._tactics(side)
        mates = [p for p in self._team(side) if p is not h]
        opponents = self._team(OTHER[side])
        bx, by = self.ball
        hx, _ = self._to_team(side, h.x, h.y)
        advantage = self._advantage(side)
        forcing = self._forcing(side, "goal")
        pressure = self._pressure_on(h)
        line = self._offside_line(side)
        best: tuple[float, _PlayerState, float, float, float, float] | None = None
        for m in mates:
            if m.slot == 0 and hx > 30:
                continue  # don't play back to the keeper from midfield
            running = m.running(self.t)
            if running:
                # A through ball: into the space the runner is attacking, not to their feet.
                rx, ry = m.run_to
                ahead = math.hypot(rx - m.x, ry - m.y)
                lead = min(ahead, max(m.speed, 4.0) * 1.2)
                tx = m.x + (rx - m.x) / ahead * lead if ahead > 0.5 else m.x
                ty = m.y + (ry - m.y) / ahead * lead if ahead > 0.5 else m.y
            else:
                lead = 0.45 if m.speed > 3 else 0.0
                tx, ty = m.x + m.vx * lead, m.y + m.vy * lead
            dist = math.hypot(tx - bx, ty - by)
            if dist < 5 or dist > 48:
                continue
            lane = min((_seg_dist(o.x, o.y, bx, by, tx, ty) for o in opponents), default=10)
            open_space = min((math.hypot(o.x - tx, o.y - ty) for o in opponents), default=10)
            progress = self._to_team(side, tx, ty)[0] - hx
            score = (
                progress * (0.3 + 0.2 * tactics.directness + 0.25 * advantage)
                + min(open_space, 10) * 1.1
                + min(lane, 6) * 1.2
                - dist * (0.14 - 0.08 * tactics.directness)
                + self.rng.random() * 4
            )
            if running:
                score += 2 + 3 * tactics.directness  # the run is there to be found
            beyond = self._to_team(side, m.x, m.y)[0] - line
            if self.offside_applies and beyond > OFFSIDE_TOLERANCE_M:
                # The passer sees a clear offside coming; a marginal one is easy to misjudge.
                score -= 2 + 6 * min(beyond, 1.5) + 1.5 * self.offsides[side]
            if forcing and forcing.player_number == m.player.number:
                score += 12
            if best is None or score > best[0]:
                best = (score, m, tx, ty, lane, open_space)
        if best is None:
            return False
        _, target, tx, ty, lane, open_space = best
        dist = math.hypot(tx - bx, ty - by)
        speed = _clamp(13 + dist * 0.18, 13, 23)  # m/s, longer balls are struck harder
        difficulty = _clamp(
            dist / 45 * 0.5 + pressure * 0.3 + (1 - min(lane, 6) / 6) * 0.3, 0.02, 0.99
        )
        attributes = {
            "pass_distance_m": round(dist, 1),
            "pass_difficulty": round(difficulty, 2),
            "ball_speed_kmh": round(speed * 3.6, 1),
            "pressure_level": round(pressure, 2),
        }
        offside = self.offside_applies and self._offside(target, line)
        self.offside_applies = True
        if offside:
            self._emit(
                "pass", h, side, (bx, by), to=(tx, ty), outcome="fail", target=target, **attributes
            )
            spot = (target.x, target.y)
            self._emit("offside", target, side, spot, outcome="fail")
            self.offsides[side] += 1
            self._set_restart(OTHER[side], "free_kick", spot, self._stoppage("free_kick"))
            return True
        # The final third is where possession is hardest to keep, more so when marked tightly.
        final_third = self._to_team(side, tx, ty)[0] > 70
        marked = final_third and open_space < 4
        success_p = _clamp(
            0.78
            + h.player.passing * 0.34
            - dist / 250
            - pressure * 0.12
            - (0.12 if lane < 1.0 else 0.0)
            - (0.14 if final_third else 0.0)
            - (0.12 if marked else 0.0)
            + 0.1 * advantage,
            0.15,
            0.97,
        )
        success = self.rng.random() < success_p
        end: tuple[float, float] = (tx, ty)
        receiver: _PlayerState | None = target
        restarts: Side = OTHER[side]  # who restarts if it goes out: the side that didn't touch it
        if not success:
            roll = self.rng.random()
            exit_point = _exit_point(bx, by, tx, ty)
            if roll < 0.4 and math.hypot(exit_point[0] - tx, exit_point[1] - ty) < 22:
                end, receiver = exit_point, None  # misplaced: it runs out of play
            elif roll < 0.55:
                # Overhit or underhit into space: whoever is nearest collects it.
                ox = _clamp(tx + (tx - bx) * 0.25, 0.5, L - 0.5)
                oy = _clamp(ty + (ty - by) * 0.25, 0.5, W - 0.5)
                end = (ox, oy)
                receiver = min(opponents, key=lambda o: math.hypot(o.x - ox, o.y - oy))
            else:
                interceptor = min(opponents, key=lambda o: _seg_dist(o.x, o.y, bx, by, tx, ty))
                end = self._closest_on_segment(interceptor, bx, by, tx, ty)
                receiver = interceptor
                own_x, own_y = self._to_team(interceptor.side, *end)
                if own_x < 16 and self.rng.random() < 0.25:
                    # Cleared behind under pressure near goal: a corner to the attacking side.
                    corner_y = _clamp(own_y + self.rng.uniform(-10, 10), 2, W - 2)
                    end = self._from_team(interceptor.side, 0.0, corner_y)
                    receiver = None
                    restarts = side  # the defender touched it last
        flight_ms = int(math.hypot(end[0] - bx, end[1] - by) / speed * 1000) + TICK_MS
        if receiver is not None:
            # Weight it (or let it roll) so whoever collects it gets there with the ball.
            eta = math.hypot(end[0] - receiver.x, end[1] - receiver.y) / max(
                receiver.speed, 0.7 * receiver.player.top_speed_mps
            )
            flight_ms = int(_clamp(eta * 1000, flight_ms, 3_200 if receiver is target else 5_000))
        outcome: Outcome = "success" if success else "fail"
        self._emit(
            "pass", h, side, (bx, by), to=(tx, ty), outcome=outcome, target=target, **attributes
        )
        self.holder = None
        self.flight = _Flight(
            bx, by, end[0], end[1], self.t, self.t + flight_ms, receiver, restart_side=restarts
        )
        return True

    @staticmethod
    def _closest_on_segment(
        p: _PlayerState, ax: float, ay: float, bx: float, by: float
    ) -> tuple[float, float]:
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy or 1.0
        u = _clamp(((p.x - ax) * dx + (p.y - ay) * dy) / length2, 0.2, 1)
        return ax + u * dx, ay + u * dy

    def _shoot(self, h: _PlayerState, goal_d: float, angle: float, xg: float) -> None:
        side = h.side
        self.offside_applies = True
        gx, gy = self._from_team(side, L, 34 + self.rng.uniform(-3.5, 3.5))
        forcing = self._forcing(side, "goal")
        finishing = self.story.finishing[0 if side == "home" else 1]
        if forcing and goal_d < 26:
            outcome: Outcome = "goal"
        else:
            # Storyline beats supply the scripted goals, so natural conversion is kept modest.
            p_goal = xg * (0.5 + 0.6 * h.player.finishing) * finishing * 0.45
            roll = self.rng.random()
            outcome = (
                "goal"
                if roll < p_goal
                else (
                    "saved"
                    if roll < p_goal + (1 - p_goal) * 0.42
                    else "blocked" if roll < p_goal + (1 - p_goal) * 0.65 else "off_target"
                )
            )
        speed_kmh = round(
            _clamp(58 + h.player.finishing * 32 + self.rng.uniform(0, 26), 50, 125), 1
        )
        self._emit(
            "shot", h, side, self.ball, to=(gx, gy), outcome=outcome, ball_speed_kmh=speed_kmh
        )
        keeper = next((p for p in self._team(OTHER[side]) if p.slot == 0), None)
        bx, by = self.ball
        speed = speed_kmh / 3.6

        def fly(
            x1: float,
            y1: float,
            receiver: _PlayerState | None,
            out: bool = True,
            restart: Side = OTHER[side],
        ) -> None:
            ms = int(math.hypot(x1 - bx, y1 - by) / speed * 1000) + TICK_MS
            self.holder = None
            self.flight = _Flight(bx, by, x1, y1, self.t, self.t + ms, receiver, restart, out)

        def behind() -> None:  # turned behind the goal line: a corner to the shooting side
            post = self._to_team(side, gx, gy)[1] + self.rng.choice((-1, 1)) * self.rng.uniform(
                4, 8
            )
            fly(*self._from_team(side, L - 0.2, _clamp(post, 20, 48)), None, restart=side)

        if outcome == "goal":
            self._emit("goal", h, side, self.ball, outcome="goal")
            if forcing:
                self.pending_beats.remove(forcing)
            fly(*self._from_team(side, L + 1.2, self._to_team(side, gx, gy)[1]), None, out=False)
            self._stop_for_kickoff(OTHER[side], GOAL_PAUSE_MS)
        elif outcome == "saved" and keeper:
            self._emit("save", keeper, OTHER[side], (keeper.x, keeper.y), outcome="success")
            if self.rng.random() < 0.35:
                behind()  # parried round the post
            else:
                fly(keeper.x, keeper.y, keeper)
        elif outcome == "blocked":
            blocker = min(self._team(OTHER[side]), key=lambda o: math.hypot(o.x - h.x, o.y - h.y))
            if self.rng.random() < 0.3:
                behind()  # deflected wide
            else:
                fly(blocker.x, blocker.y, blocker)
        else:  # wide or over: out for a goal kick
            wide = self._to_team(side, gx, gy)[1] + self.rng.choice((-1, 1)) * self.rng.uniform(
                5, 9
            )
            fly(*self._from_team(side, L - 0.2, _clamp(wide, 20, 48)), None)

    def _try_tackle(self, h: _PlayerState) -> bool:
        if h.slot == 0 and self._to_team(h.side, h.x, h.y)[0] < 16.5:
            return False  # a keeper with the ball in their own box is not challenged
        side = OTHER[h.side]
        tackler = min(self._team(side), key=lambda o: math.hypot(o.x - h.x, o.y - h.y))
        if math.hypot(tackler.x - h.x, tackler.y - h.y) > 1.5:
            return False
        rate = 0.75 * (0.7 + 0.3 * tackler.player.work_rate) * (1 + 0.15 * self._advantage(side))
        red_beat = self._forcing(side, "red_card")
        if not red_beat and self.rng.random() > rate * DT:
            return False
        if red_beat or self.rng.random() < 0.4:
            self._foul(tackler, h, red_beat)
            return True
        self._emit("tackle", tackler, side, (tackler.x, tackler.y), outcome="success")
        if min(h.y, W - h.y) < 10 and self.rng.random() < 0.4:
            # Won near the touchline, but poked out of play: a throw-in to the side that had it.
            spot = (h.x, 0.3 if h.y < W / 2 else W - 0.3)
            self._set_restart(h.side, "throw", spot, self._stoppage("throw"))
            return True
        self._give(tackler, hold_ms=600)
        return True

    def _foul(self, fouler: _PlayerState, victim: _PlayerState, red_beat: Beat | None) -> None:
        self._emit("foul", fouler, fouler.side, (fouler.x, fouler.y), outcome="success")
        card: Literal["yellow", "red"] | None = None
        if red_beat:
            card = "red"
            self.pending_beats.remove(red_beat)
        elif self.rng.random() < 0.13:
            fouler.yellows += 1
            card = "red" if fouler.yellows == 2 else "yellow"
        if card:
            self._emit("card", fouler, fouler.side, (fouler.x, fouler.y), card_color=card)
            if card == "red":
                fouler.on_pitch = False
        self._set_restart(victim.side, "free_kick", self.ball, self._stoppage("free_kick"))
        self.restart_taker = victim

    # --- Substitutions -----------------------------------------------------------------------

    def _substitutions(self) -> None:
        for side in ("home", "away"):
            due = self.subs_due[side]
            if not due or self.t < due[0] or self.t >= self.dead_until_ms:
                continue  # changes are made while the ball is dead
            due.pop(0)
            outfield = [p for p in self._team(side) if p.slot != 0 and p is not self.restart_taker]
            bench = [b for b in self.bench[side] if b.role != "gk"]
            if not outfield or not bench:
                continue
            off = self.rng.choice(outfield)
            on = next((b for b in bench if b.role == off.player.role), bench[0])
            self.bench[side].remove(on)
            self._emit("substitution", off, side, (off.x, off.y), target=on)
            if self.restart and self.restart[1] != "kickoff":
                self.dead_until_ms += int(self.rng.uniform(*SUBSTITUTION_MS))
            off.player = on
            off.distance = 0.0
            off.run_until_ms = 0
            self._settle(off)
            slot_index = self.players.index(off)
            self.frames.occupants[slot_index].append((self.t, on.player_id))

    # --- Runs in behind ------------------------------------------------------------------------

    def _update_runs(self) -> None:
        """Forwards (and sometimes midfielders) start timed runs behind the defence when a
        teammate has the ball in a position to find them."""
        h = self.holder
        if not h or self.flight or self._stopped():
            return
        side = h.side
        hx, _ = self._to_team(side, h.x, h.y)
        if hx < 35:
            return
        tactics = self._tactics(side)
        line = self._offside_line(side)
        for p in self._team(side):
            if p is h or p.running(self.t) or self.t < p.next_run_ms:
                continue
            role = self._role(p)
            if role in ("gk", "def"):
                continue
            px, py = self._to_team(side, p.x, p.y)
            if line - px > 14 or px > line + OFFSIDE_TOLERANCE_M:
                continue  # too deep to threaten, or already offside
            rate = (0.07 if role == "fwd" else 0.02) * (0.4 + tactics.runs_in_behind)
            if self.rng.random() >= rate * DT:
                continue
            depth = self.rng.uniform(8, 16)
            ty = _clamp(py + (34 - py) * 0.3 + self.rng.uniform(-6, 6), 6, W - 6)
            p.run_to = self._from_team(side, min(line + depth, L - 7), ty)
            p.run_burst_ms = self.t + int(self.rng.uniform(500, 1_000))
            p.run_until_ms = self.t + int(self.rng.uniform(2_600, 4_000))
            p.run_effort = self.rng.uniform(0.84, 1.0)
            p.next_run_ms = p.run_until_ms + int(self.rng.uniform(4_000, 10_000))
            # The carrier has seen the run and looks to release it before it strays offside.
            release = self.t + int(self.rng.uniform(300, 1_400))
            self.next_action_ms = min(self.next_action_ms, release)

    # --- Movement ------------------------------------------------------------------------------

    def _move_players(self) -> None:
        targets = self._targets()
        for p in self.players:
            if not p.on_pitch:
                continue
            tx, ty, urgency = targets[id(p)]
            # Reaction: a player takes a moment to read a change; the carrier and the receiver
            # of a pass are already reacting to the ball.
            if p is self.holder or (self.flight and p is self.flight.receiver):
                p.tx, p.ty = tx, ty
            else:
                p.tx, p.ty = _ease(p.tx, tx, p.lag_s), _ease(p.ty, ty, p.lag_s)
            gx, gy = p.tx, p.ty
            if urgency < 0.5 and p is not self.holder:  # nobody stands perfectly still
                seconds = self.t / 1000
                gx += DRIFT_M * math.sin(2 * math.pi * seconds / p.sway[0] + p.sway[1])
                gy += DRIFT_M * math.sin(2 * math.pi * seconds / p.sway[2] + p.sway[3])
            dx, dy = gx - p.x, gy - p.y
            d = math.hypot(dx, dy)
            top = p.player.top_speed_mps
            # Arrive: never faster than the player could still brake from in the distance left.
            # Positional moves also ease in as the spot nears (a few meters off is a walk, not a
            # jog); pressing, runs, and getting to the ball go flat out.
            want = min(top * urgency, math.sqrt(2 * DECEL_MAX * max(d - 0.3, 0.0)))
            if urgency < 0.5:
                want = min(want, d * APPROACH_GAIN)
            wvx, wvy = (dx / d * want, dy / d * want) if d > 0.05 else (0.0, 0.0)
            ax, ay = wvx - p.vx, wvy - p.vy
            a = math.hypot(ax, ay)
            speed = p.speed
            if want > speed:  # speeding up (or turning): athletes accelerate less near top speed
                capacity = ACCEL_FLOOR + (ACCEL_MAX - ACCEL_FLOOR) * max(0.0, 1 - speed / top)
            else:
                capacity = DECEL_MAX
            limit = capacity * DT
            if a > limit:
                ax, ay = ax / a * limit, ay / a * limit
            p.vx += ax
            p.vy += ay
            step_x, step_y = p.vx * DT, p.vy * DT
            p.x = _clamp(p.x + step_x, 0.3, L - 0.3)
            p.y = _clamp(p.y + step_y, 0.3, W - 0.3)
            p.distance += math.hypot(step_x, step_y)
            self._track_sprint(p)

    def _update_line(self, side: Side, attacking: bool, ball_x: float) -> float:
        """Move this side's back line (in its own frame) as a unit, and return it."""
        tactics = self._tactics(side)
        height = tactics.line_height
        # The block shifts about half a meter for every meter the ball moves, around a resting
        # height set by the tactics (measured with the ball on halfway).
        if attacking:
            rest = 30 + 15 * height
            target = _clamp(rest + 0.55 * (ball_x - L / 2), 12, 40 + 18 * height)
        else:
            rest = 21 + 22 * height
            target = _clamp(rest + 0.5 * (ball_x - L / 2), 8, 30 + 26 * height)
            if ball_x < 40:
                target = min(target, ball_x * 0.6)  # defend the box when play is in your third
            carrier = self.holder
            if carrier and carrier.side != side:
                # An unpressured carrier can play over the top, so the line drops off a little;
                # a side that likes the offside trap holds its ground.
                caution = 1 - 0.6 * tactics.offside_trap
                target -= 5 * (1 - self._pressure_on(carrier)) * caution
                if any(o.running(self.t) for o in self._team(carrier.side)):
                    target -= 4 * caution
            target = max(min(target, ball_x - 1), 6)
        current = self.line[side]
        stepping_up = target > current
        tau = (1.1 - 0.5 * tactics.offside_trap) if stepping_up else 0.9
        self.line[side] = _ease(current, target, tau)
        return self.line[side]

    def _press_assignments(
        self, side: Side, ball_x: float
    ) -> tuple[_PlayerState | None, _PlayerState | None]:
        """Who closes down the carrier, and who covers behind them, if this side presses now."""
        tactics = self._tactics(side)
        if not self.press_on or self.flight or self._stopped():
            return None, None
        if ball_x > 35 + 70 * tactics.press_height:
            return None, None  # the ball is beyond where this side starts pressing
        bx, by = self.ball
        outfield = [p for p in self._team(side) if p.slot != 0]
        by_distance = sorted(outfield, key=lambda p: math.hypot(p.x - bx, p.y - by))
        if not by_distance or math.hypot(by_distance[0].x - bx, by_distance[0].y - by) > 16:
            return None, None
        return by_distance[0], (by_distance[1] if len(by_distance) > 1 else None)

    def _support_spots(self, side: Side) -> dict[int, tuple[float, float]]:
        """The two teammates nearest the carrier offer angles: one short, one ahead (team frame)."""
        h = self.holder
        if not h or h.side != side or self.flight or self._stopped():
            return {}
        hx, hy = self._to_team(side, h.x, h.y)
        nearby = sorted(
            (p for p in self._team(side) if p is not h and p.slot != 0 and not p.running(self.t)),
            key=lambda p: math.hypot(p.x - h.x, p.y - h.y),
        )[:2]
        spots: dict[int, tuple[float, float]] = {}
        for i, p in enumerate(nearby):
            _, py = self._to_team(side, p.x, p.y)
            lateral = 1 if py >= hy else -1
            if i == 0:
                spots[id(p)] = (hx - 4, _clamp(hy + lateral * 11, 3, W - 3))
            else:
                spots[id(p)] = (hx + 10, _clamp(hy + lateral * 9, 3, W - 3))
        return spots

    def _carry_target(self, h: _PlayerState) -> tuple[float, float, float]:
        """Where the carrier runs with the ball: toward the most open lane that still goes
        forward, and never along the goal line."""
        if h.slot == 0 or (self._blocked_ahead(h) and self._pressure_on(h) > 0.5):
            return h.x, h.y, 0.15  # a keeper holds their ground; anyone else shields it
        side = h.side
        hx, hy = self._to_team(side, h.x, h.y)
        opponents = [self._to_team(side, o.x, o.y) for o in self._team(OTHER[side])]
        best: tuple[float, float, float, float] | None = None
        for degrees in (-55, -30, -12, 0, 12, 30, 55):
            angle = math.radians(degrees)
            px, py = hx + 7 * math.cos(angle), hy + 7 * math.sin(angle)
            if not 2 < py < W - 2 or px > L - 6:
                continue
            space = min(min((math.hypot(ox - px, oy - py) for ox, oy in opponents), default=12), 12)
            value = space + 2.5 * math.cos(angle) - (abs(py - 34) * 0.04 if px > 70 else 0)
            if best is None or value > best[0]:
                best = (value, px, py, space)
        if best is None:
            return h.x, h.y, 0.15
        _, px, py, space = best
        x, y = self._from_team(side, px, py)
        return x, y, 0.5 + 0.2 * min(space, 8) / 8

    def _targets(self) -> dict[int, tuple[float, float, float]]:
        """Each player's target position and urgency (fraction of top speed) this tick."""
        bx, by = self.ball
        out: dict[int, tuple[float, float, float]] = {}
        dead = self._stopped()
        kickoff = dead and self.restart is not None and self.restart[1] == "kickoff"
        # Turnovers are often won straight back, so teams only reshape once a possession settles;
        # until then the side that lost the ball stays in its attacking shape and counter-presses.
        if self.possession != self.shape_owner and self.t - self.possession_since >= SETTLE_MS:
            self.shape_owner = self.possession
        for side in ("home", "away"):
            team = self._team(side)
            tactics = self._tactics(side)
            attacking = self.possession == side
            shaped = self.shape_owner == side  # set up to attack
            tbx, tby = self._to_team(side, bx, by)
            formation = FORMATIONS[self.clubs[side].formation]
            reference = _back_line(self.clubs[side].formation)
            line = self._update_line(side, shaped, tbx)
            presser, cover = (None, None) if attacking else self._press_assignments(side, tbx)
            offside_line = self._offside_line(side) if attacking else L
            support = self._support_spots(side) if attacking else {}
            for p in team:
                role, sx, sy = formation[p.slot]
                px, _ = self._to_team(side, p.x, p.y)
                if kickoff:
                    kicking = self.restart[0] == side  # type: ignore[index]
                    x, y = self._kickoff_spot(side, p.slot, kicking=kicking)
                    taker = kicking and p is self._kickoff_taker(side)
                    out[id(p)] = (x, y, 0.5 if taker else 0.35)
                    continue
                if dead and p is self.restart_taker and self.restart_spot:
                    hurry = 0.8 if self.t > self.dead_until_ms else 0.6
                    out[id(p)] = (*self.restart_spot, hurry)
                    continue
                if p is self.holder and not dead:
                    out[id(p)] = self._carry_target(p)
                    continue
                if self.flight and p is self.flight.receiver:
                    out[id(p)] = (self.flight.x1, self.flight.y1, 0.95)
                    continue
                if role == "gk":
                    gx = _clamp(4 + max(0.0, line - 20) * 0.3, 3, 17)
                    gy = 34 + (tby - 34) * 0.15
                    out[id(p)] = (*self._from_team(side, gx, gy), 0.6)
                    continue
                if p is presser:
                    out[id(p)] = (bx, by, 0.75 + 0.2 * p.player.work_rate)
                    continue
                if p is cover:
                    out[id(p)] = (*self._from_team(side, max(tbx - 6, 2), tby), 0.7)
                    continue
                if attacking and p.running(self.t):
                    if self.t < p.run_burst_ms:  # shape the run along the line, still onside
                        rx, ry = self._to_team(side, *p.run_to)
                        hold = min(px + 1.5, offside_line - 0.4)
                        out[id(p)] = (*self._from_team(side, hold, ry), 0.6)
                    else:
                        out[id(p)] = (*p.run_to, p.run_effort)
                    continue
                depth = sx - reference
                if shaped:
                    fx = line + depth * (1.0 + 0.15 * tactics.directness)
                    fy = 34 + (sy - 34) * (0.85 + 0.25 * tactics.width) + (tby - 34) * 0.12
                    spot = support.get(id(p))
                    if spot:
                        fx += (spot[0] - fx) * SUPPORT_BLEND
                        fy += (spot[1] - fy) * SUPPORT_BLEND
                    if role != "def":
                        # Stay onside, ready to run; a side that keeps getting flagged waits deeper.
                        wait = HOLD_LINE_M + 0.25 * self.offsides[side]
                        fx = min(fx, offside_line - wait)
                    urgency = 0.32 + 0.1 * p.player.work_rate
                    if fx - px > 12:  # break forward after winning it back; sprint if far behind
                        urgency = max(p.transition_effort, 0.88 if fx - px > 28 else 0.0)
                else:
                    fx = line + depth * (0.62 - 0.12 * tactics.compactness)
                    fy = (
                        34
                        + (sy - 34) * (0.85 - 0.25 * tactics.compactness)
                        + (tby - 34) * (0.2 + 0.15 * tactics.compactness)
                    )
                    urgency = 0.34 + 0.12 * p.player.work_rate
                    if px - fx > 12:  # caught upfield: a recovery run, a sprint if badly exposed
                        urgency = max(p.transition_effort, 0.9 if px - fx > 28 else 0.0)
                fx, fy = _clamp(fx, 2, L - 2), _clamp(fy, 2, W - 2)
                out[id(p)] = (*self._from_team(side, fx, fy), urgency)
        return out

    # --- Physical events -----------------------------------------------------------------------

    def _track_sprint(self, p: _PlayerState) -> None:
        speed = p.speed
        if speed >= SPRINT_MPS:
            if p.sprint_ms == 0:
                p.sprint_from = (p.x, p.y)
                p.sprint_top = 0.0
                p.sprint_len = 0.0
            p.sprint_ms += TICK_MS
            p.sprint_top = max(p.sprint_top, speed)
            p.sprint_len += speed * DT
        elif p.sprint_ms:
            if p.sprint_ms >= SPRINT_MIN_MS:
                self._emit(
                    "sprint",
                    p,
                    p.side,
                    p.sprint_from,
                    to=(p.x, p.y),
                    top_speed_kmh=round(p.sprint_top * 3.6, 1),
                    sprint_distance_m=round(p.sprint_len, 1),
                )
            p.sprint_ms = 0

    def _defenders_in_cone(self, h: _PlayerState) -> int:
        """Opponents (keeper excluded) inside the triangle from the shooter to the goalposts."""
        hx, hy = self._to_team(h.side, h.x, h.y)
        count = 0
        for o in self._team(OTHER[h.side]):
            if o.slot == 0:
                continue
            ox, oy = self._to_team(h.side, o.x, o.y)
            if not hx < ox < L:
                continue
            u = (ox - hx) / max(L - hx, 0.1)  # 0 at the shooter, 1 on the goal line
            half_width = 3.66 * u + 0.5 * (1 - u)
            centre = hy + (34 - hy) * u
            if abs(oy - centre) < half_width + 0.5:
                count += 1
        return count

    def _blocked_ahead(self, h: _PlayerState) -> bool:
        """An opponent within 8 m in front of the carrier, inside a cone toward goal."""
        hx, hy = self._to_team(h.side, h.x, h.y)
        for o in self._team(OTHER[h.side]):
            ox, oy = self._to_team(h.side, o.x, o.y)
            ahead = ox - hx
            if 0.5 < ahead < 8 and abs(oy - hy) < ahead * 0.8 + 1:
                return True
        return False

    def _pressure_on(self, h: _PlayerState) -> float:
        nearest = min(
            (math.hypot(o.x - h.x, o.y - h.y) for o in self._team(OTHER[h.side])), default=20
        )
        return _clamp(1 - nearest / 6, 0, 1)

    def _pressure_events(self) -> None:
        h = self.holder
        if not h or self.flight or self._stopped():
            return
        for o in self._team(OTHER[h.side]):
            d = math.hypot(o.x - h.x, o.y - h.y)
            closing = ((h.x - o.x) * o.vx + (h.y - o.y) * o.vy) / max(d, 0.1)
            if d < 3.0 and closing > 1.5 and self.t - o.last_pressure_ms > 15_000:
                o.last_pressure_ms = self.t
                self._emit("pressure", o, o.side, (o.x, o.y), pressure_level=round(1 - d / 3.0, 2))

    # --- Output ------------------------------------------------------------------------------

    def _record_frame(self) -> None:
        d = self.frames.data
        d.append(self.ball[0])
        d.append(self.ball[1])
        for p in self.players:
            if p.on_pitch:
                d.append(p.x)
                d.append(p.y)
            else:
                d.append(math.nan)
                d.append(math.nan)

    def _emit(
        self,
        kind: EventType,
        actor: _PlayerState | None,
        side: Side | None,
        at: tuple[float, float] | None,
        to: tuple[float, float] | None = None,
        outcome: Outcome | None = None,
        target: _PlayerState | Player | None = None,
        **attributes: float | str,
    ) -> None:
        self.n += 1
        target_player = target.player if isinstance(target, _PlayerState) else target
        if actor is not None:
            attributes.setdefault("player_speed_kmh", round(actor.speed * 3.6, 1))
            attributes.setdefault("distance_covered_m", round(actor.distance, 1))
        self.events.append(
            MatchEvent(
                event_id=f"evt_{self.n:06d}",
                match_id=self.match_id,
                minute=self.t // 60_000,
                second=self.t // 1000 % 60,
                match_clock_ms=self.t,
                type=kind,
                team_id=self.clubs[side].club_id if side else None,
                player_id=actor.player.player_id if actor else None,
                target_player_id=target_player.player_id if target_player else None,
                location=_point(at) if at else None,
                end_location=_point(to) if to else None,
                outcome=outcome,
                attributes=EventAttributes(**attributes),
            )
        )


def _point(p: tuple[float, float]) -> PitchPoint:
    return PitchPoint(
        x=round(_clamp(p[0], 0, L) / L * 100, 2), y=round(_clamp(p[1], 0, W) / W * 100, 2)
    )
