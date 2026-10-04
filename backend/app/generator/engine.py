"""Tick-based synthetic match engine.

The match is simulated in 0.2 s ticks. Every tick, each player moves toward a target (their
formation slot shifted by the ball, a run into space, closing down the ball, or the ball itself)
with realistic acceleration and top speed, and the ball carrier decides when to pass, shoot, or
keep going. Events are emitted as they happen, so they are always consistent with the tracking
data: the ball is where the events say it is, and speeds, distance covered, and sprints come out
of the movement rather than being invented.

Coordinates are meters internally (105 x 68); events and frames use the normalized 0-100 pitch.
"""

from __future__ import annotations

import math
import random
from array import array
from dataclasses import dataclass, field
from typing import Literal

from app.generator.storylines import Beat, Side, Storyline
from app.generator.world import FORMATIONS, Club, Player
from app.models import EventAttributes, MatchEvent, TrackingFrame
from app.models.common import PitchPoint
from app.models.events import EventType, Outcome
from app.models.tracking import PlayerPosition

TICK_MS = 200
FRAME_EVERY = 2  # record tracking every 2 ticks (2.5 Hz); consumers interpolate
L, W = 105.0, 68.0
HALF_MS = 45 * 60_000
ACCEL = 4.0  # m/s^2
SPRINT_MPS = 7.0  # 25.2 km/h, the usual high-intensity threshold
SPRINT_MIN_MS = 1_000
GOAL_PAUSE_MS = 40_000
OTHER: dict[Side, Side] = {"home": "away", "away": "home"}


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _seg_dist(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Distance from point p to segment a-b."""
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else _clamp(((px - ax) * dx + (py - ay) * dy) / length2, 0, 1)
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def expected_goals(distance_m: float, angle_rad: float) -> float:
    """A simple location xG: falls off with distance and with how wide the shot is."""
    return _clamp(
        0.9 * math.exp(-distance_m / 8.0) * (0.35 + 0.65 * math.cos(angle_rad)), 0.01, 0.8
    )


@dataclass(eq=False)
class _PlayerState:
    player: Player
    side: Side
    slot: int  # 0-10, formation slot
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    distance: float = 0.0
    on_pitch: bool = True
    yellows: int = 0
    sprint_ms: int = 0
    sprint_from: tuple[float, float] = (0.0, 0.0)
    sprint_top: float = 0.0
    sprint_len: float = 0.0
    last_pressure_ms: int = -60_000

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)


@dataclass
class _Flight:
    """The ball in the air: from where to where, when it lands, and who ends up with it."""

    x0: float
    y0: float
    x1: float
    y1: float
    t0: int
    t1: int
    receiver: _PlayerState | None  # None: the ball runs out of play
    restart_side: Side | None = None  # who restarts if it goes out


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
        """The frame at any instant, linearly interpolated between recorded frames."""
        k = _clamp(clock_ms / self.FRAME_MS, 0, self.count - 1)
        k0 = int(k)
        k1 = min(k0 + 1, self.count - 1)
        f = k - k0
        a, b = k0 * self.STRIDE, k1 * self.STRIDE
        d = self.data
        players = []
        for slot in range(22):
            i0, i1 = a + 2 + slot * 2, b + 2 + slot * 2
            x = d[i0] + (d[i1] - d[i0]) * f
            y = d[i0 + 1] + (d[i1 + 1] - d[i0 + 1]) * f
            if math.isnan(x):
                continue  # sent off
            speed = math.hypot(d[i1] - d[i0], d[i1 + 1] - d[i0 + 1]) / (self.FRAME_MS / 1000)
            players.append(
                PlayerPosition(
                    player_id=self._occupant(slot, clock_ms),
                    team_id=self.teams[slot],
                    x=round(x / L * 100, 2),
                    y=round(y / W * 100, 2),
                    speed_kmh=round(speed * 3.6, 1),
                )
            )
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
                self.players.append(_PlayerState(player, side, slot, x, y))
                self.frames.occupants.append([(0, player.player_id)])
                self.frames.teams.append(club.club_id)
            self.bench[side] = list(club.squad[11:])
        self.holder: _PlayerState | None = None
        self.flight: _Flight | None = None
        self.ball = (L / 2, W / 2)
        self.possession: Side = "home"
        self.next_action_ms = 0
        self.carry_from = (L / 2, W / 2)
        self.press_on = True  # whether the defending side presses this possession
        self.dead_until_ms = 0
        self.restart: tuple[Side, str] | None = None  # (side, reason) taking the next restart
        self.pending_beats: list[Beat] = sorted(storyline.beats, key=lambda b: b.minute)
        self.subs_due: dict[Side, list[int]] = {
            side: sorted(self.rng.randint(58 * 60_000, 82 * 60_000) for _ in range(3))
            for side in ("home", "away")
        }
        self.full_time_ms = 90 * 60_000 + self.rng.randint(1, 5) * 60_000

    # --- Main loop ----------------------------------------------------------------------------

    def run(self) -> MatchResult:
        self._kickoff("home")
        second_half = False
        tick = 0
        while self.t < self.full_time_ms:
            if not second_half and self.t >= HALF_MS:
                self._emit("half_end", None, None, None)
                second_half = True
                self._reset_positions("away")
                self._kickoff("away")
            self._substitutions()
            self._update_ball()
            self._update_holder()
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

    def _kickoff_spot(self, side: Side, slot: int, kicking: bool) -> tuple[float, float]:
        club = self.clubs[side]
        _, sx, sy = FORMATIONS[club.formation][slot]
        x = min(sx * 0.62, 49.5)
        if kicking and slot >= 9:
            x, sy = 51.0, 34.0 + (2.5 if slot == 9 else -2.5)
        return self._from_team(side, x, sy)

    # --- Restarts ---------------------------------------------------------------------------

    def _reset_positions(self, kicking: Side) -> None:
        for p in self.players:
            if p.on_pitch:
                p.x, p.y = self._kickoff_spot(p.side, p.slot, kicking=p.side == kicking)
                p.vx = p.vy = 0.0

    def _kickoff(self, side: Side) -> None:
        team = self._team(side)
        taker = next((p for p in team if p.slot >= 9), None) or team[-1]
        self.ball = (L / 2, W / 2)
        taker.x, taker.y = self._from_team(side, 51.5, 34.0)
        self._give(taker, hold_ms=900)
        self._emit("kickoff", taker, side, self.ball, outcome="success")

    def _give(self, player: _PlayerState, hold_ms: int | None = None) -> None:
        self.holder = player
        self.flight = None
        self.possession = player.side
        if hold_ms is None:
            pressure = self._pressure_on(player)
            hold_ms = int(self.rng.uniform(1_000, 2_900) * (1 - 0.4 * pressure))
        self.next_action_ms = self.t + hold_ms
        self.carry_from = (player.x, player.y)
        # Teams press selectively; the side on top presses more often.
        self.press_on = self.rng.random() < 0.45 + 0.2 * self._advantage(OTHER[player.side])

    # --- Ball -------------------------------------------------------------------------------

    def _update_ball(self) -> None:
        if self.flight:
            f = self.flight
            u = _clamp((self.t - f.t0) / max(1, f.t1 - f.t0), 0, 1)
            self.ball = (f.x0 + (f.x1 - f.x0) * u, f.y0 + (f.y1 - f.y0) * u)
            if self.t >= f.t1:
                if f.receiver:
                    self._give(f.receiver)
                else:  # out of play: a throw-in for the other side after a short stoppage
                    self.flight = None
                    self.possession = f.restart_side or self.possession
                    self.dead_until_ms = self.t + int(self.rng.uniform(6_000, 12_000))
                    self.restart = (self.possession, "throw")
        elif self.holder:
            direction = 1 if self.holder.side == "home" else -1  # home attacks toward x = L
            self.ball = (_clamp(self.holder.x + 0.6 * direction, 0, L), self.holder.y)

    def _update_holder(self) -> None:
        h = self.holder
        if not h or self.flight or self.t < self.dead_until_ms:
            if self.restart and self.t >= self.dead_until_ms:
                side, kind = self.restart
                self.restart = None
                if kind == "kickoff":
                    self._kickoff(side)
                else:  # throw-in: the nearest player of that side takes it
                    bx, by = self.ball
                    taker = min(self._team(side), key=lambda q: math.hypot(q.x - bx, q.y - by))
                    self._give(taker, hold_ms=900)
            return
        if self._try_tackle(h):
            return
        hx, _ = self._to_team(h.side, h.x, h.y)
        carried = math.hypot(h.x - self.carry_from[0], h.y - self.carry_from[1])
        if self.t >= self.next_action_ms or hx > 101 or carried > 14:
            self._decide(h)

    # --- Decisions ----------------------------------------------------------------------------

    def _decide(self, h: _PlayerState) -> None:
        hx, hy = self._to_team(h.side, h.x, h.y)
        goal_d = math.hypot(L - hx, 34 - hy)
        angle = abs(math.atan2(hy - 34, L - hx))
        xg = expected_goals(goal_d, angle)
        forcing = self._forcing(h.side, "goal")
        shot_p = 0.0
        if goal_d < 26 and angle < 1.1:
            shot_p = _clamp(xg * 0.8, 0, 0.5) * (1 + 0.3 * self._advantage(h.side))
            # Defenders between the shooter and goal close the shooting lane.
            shot_p *= 0.7 ** self._defenders_in_cone(h)
            if forcing and goal_d < 26:
                shot_p = (
                    0.9
                    if (not forcing.player_number or forcing.player_number == h.player.number)
                    else 0.35
                )
        if self.rng.random() < shot_p:
            self._shoot(h, goal_d, angle, xg)
            return
        if self._pass(h):
            return
        self.next_action_ms = self.t + int(self.rng.uniform(400, 900))  # keep the ball

    def _pass(self, h: _PlayerState) -> bool:
        side = h.side
        mates = [p for p in self._team(side) if p is not h]
        opponents = self._team(OTHER[side])
        bx, by = self.ball
        hx, _ = self._to_team(side, h.x, h.y)
        advantage = self._advantage(side)
        forcing = self._forcing(side, "goal")
        pressure = self._pressure_on(h)
        best: tuple[float, _PlayerState, float, float, float] | None = None
        for m in mates:
            if m.slot == 0 and hx > 30:
                continue  # don't play back to the keeper from midfield
            lead = 0.45 if m.speed > 3 else 0.0
            tx, ty = m.x + m.vx * lead, m.y + m.vy * lead
            dist = math.hypot(tx - bx, ty - by)
            if dist < 5 or dist > 48:
                continue
            lane = min((_seg_dist(o.x, o.y, bx, by, tx, ty) for o in opponents), default=10)
            open_space = min((math.hypot(o.x - tx, o.y - ty) for o in opponents), default=10)
            progress = self._to_team(side, tx, ty)[0] - hx
            score = (
                progress * (0.35 + 0.25 * advantage)
                + min(open_space, 10) * 1.1
                + min(lane, 6) * 1.2
                - dist * 0.1
                + self.rng.random() * 4
            )
            if forcing and forcing.player_number == m.player.number:
                score += 12
            if best is None or score > best[0]:
                best = (score, m, tx, ty, lane, open_space)
        if best is None:
            return False
        _, target, tx, ty, lane, open_space = best
        # The final third is where possession is hardest to keep, more so when marked tightly.
        final_third = self._to_team(side, tx, ty)[0] > 70
        marked = final_third and open_space < 4
        dist = math.hypot(tx - bx, ty - by)
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
        difficulty = _clamp(
            dist / 45 * 0.5 + pressure * 0.3 + (1 - min(lane, 6) / 6) * 0.3, 0.02, 0.99
        )
        speed = _clamp(13 + dist * 0.18, 13, 23)  # m/s, longer balls are struck harder
        end: tuple[float, float] = (tx, ty)
        receiver: _PlayerState | None = target
        if not success:
            if self.rng.random() < 0.35:
                # Overhit: the ball runs on and out, and the opponent restarts.
                end = (
                    _clamp(tx + (tx - bx) * 0.25, 0.5, L - 0.5),
                    _clamp(ty + (ty - by) * 0.25, 0.5, W - 0.5),
                )
                receiver = None
            else:
                interceptor = min(opponents, key=lambda o: _seg_dist(o.x, o.y, bx, by, tx, ty))
                end = self._closest_on_segment(interceptor, bx, by, tx, ty)
                receiver = interceptor
        flight_ms = int(math.hypot(end[0] - bx, end[1] - by) / speed * 1000) + TICK_MS
        self._emit(
            "pass",
            h,
            side,
            (bx, by),
            to=(tx, ty),
            outcome="success" if success else "fail",
            target=target,
            pass_distance_m=round(dist, 1),
            pass_difficulty=round(difficulty, 2),
            ball_speed_kmh=round(speed * 3.6, 1),
            pressure_level=round(pressure, 2),
        )
        self.holder = None
        self.flight = _Flight(
            bx, by, end[0], end[1], self.t, self.t + flight_ms, receiver, restart_side=OTHER[side]
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
        speed = round(_clamp(58 + h.player.finishing * 32 + self.rng.uniform(0, 26), 50, 125), 1)
        self._emit("shot", h, side, self.ball, to=(gx, gy), outcome=outcome, ball_speed_kmh=speed)
        keeper = next((p for p in self._team(OTHER[side]) if p.slot == 0), None)
        if outcome == "goal":
            self._emit("goal", h, side, self.ball, outcome="goal")
            if forcing:
                self.pending_beats.remove(forcing)
            self.holder = self.flight = None
            self.ball = (gx, gy)
            # Players walk back to kickoff positions during the pause (see _targets).
            self.dead_until_ms = self.t + GOAL_PAUSE_MS
            self.restart = (OTHER[side], "kickoff")
        elif outcome == "saved" and keeper:
            self._emit("save", keeper, OTHER[side], (keeper.x, keeper.y), outcome="success")
            self._give(keeper, hold_ms=2_500)
        elif outcome == "blocked":
            blocker = min(self._team(OTHER[side]), key=lambda o: math.hypot(o.x - h.x, o.y - h.y))
            self._give(blocker, hold_ms=700)
        elif keeper:
            self._give(keeper, hold_ms=6_000)  # goal kick

    def _try_tackle(self, h: _PlayerState) -> bool:
        side = OTHER[h.side]
        tackler = min(self._team(side), key=lambda o: math.hypot(o.x - h.x, o.y - h.y))
        if math.hypot(tackler.x - h.x, tackler.y - h.y) > 1.5:
            return False
        rate = 0.36 * (0.7 + 0.3 * tackler.player.work_rate) * (1 + 0.15 * self._advantage(side))
        red_beat = self._forcing(side, "red_card")
        if not red_beat and self.rng.random() > rate * TICK_MS / 1000:
            return False
        if red_beat or self.rng.random() < 0.26:
            self._foul(tackler, h, red_beat)
            return True
        self._emit("tackle", tackler, side, (tackler.x, tackler.y), outcome="success")
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
        self._give(victim, hold_ms=9_000)  # free kick
        self.dead_until_ms = self.t + 8_000

    # --- Substitutions -----------------------------------------------------------------------

    def _substitutions(self) -> None:
        for side in ("home", "away"):
            due = self.subs_due[side]
            if not due or self.t < due[0] or self.holder is None or self.holder.side == side:
                continue
            due.pop(0)
            outfield = [p for p in self._team(side) if p.slot != 0 and p is not self.holder]
            bench = [b for b in self.bench[side] if b.role != "gk"]
            if not outfield or not bench:
                continue
            off = self.rng.choice(outfield)
            on = next((b for b in bench if b.role == off.player.role), bench[0])
            self.bench[side].remove(on)
            self._emit("substitution", off, side, (off.x, off.y), target=on)
            off.player = on
            off.distance = 0.0
            slot_index = self.players.index(off)
            self.frames.occupants[slot_index].append((self.t, on.player_id))

    # --- Movement ------------------------------------------------------------------------------

    def _move_players(self) -> None:
        dt = TICK_MS / 1000
        targets = self._targets()
        for p in self.players:
            if not p.on_pitch:
                continue
            tx, ty, urgency = targets[id(p)]
            dx, dy = tx - p.x, ty - p.y
            d = math.hypot(dx, dy)
            max_speed = p.player.top_speed_mps * urgency
            want = min(max_speed, d / 1.2)
            wvx, wvy = (dx / d * want, dy / d * want) if d > 0.05 else (0.0, 0.0)
            ax, ay = wvx - p.vx, wvy - p.vy
            a = math.hypot(ax, ay)
            limit = ACCEL * dt
            if a > limit:
                ax, ay = ax / a * limit, ay / a * limit
            p.vx += ax
            p.vy += ay
            step_x, step_y = p.vx * dt, p.vy * dt
            p.x = _clamp(p.x + step_x, 0.3, L - 0.3)
            p.y = _clamp(p.y + step_y, 0.3, W - 0.3)
            p.distance += math.hypot(step_x, step_y)
            self._track_sprint(p)

    def _targets(self) -> dict[int, tuple[float, float, float]]:
        bx, by = self.ball
        out: dict[int, tuple[float, float, float]] = {}
        dead = (
            self.t < self.dead_until_ms
            and self.restart is not None
            and self.restart[1] == "kickoff"
        )
        for side in ("home", "away"):
            team = self._team(side)
            in_possession = self.possession == side
            tbx, tby = self._to_team(side, bx, by)
            advance = (tbx - 52.5) * (0.55 if in_possession else 0.45)
            # Out of possession and deep in their own half, a side drops into a narrow low block.
            low_block = not in_possession and tbx < 35
            depth = 1.0 if in_possession else 0.6 if low_block else 0.72
            width = 1.0 if in_possession else 0.68 if low_block else 0.78
            lateral = (tby - 34) * (0.18 if in_possession else 0.35)
            formation = FORMATIONS[self.clubs[side].formation]
            presser: _PlayerState | None = None
            cover: _PlayerState | None = None
            if not in_possession and not dead and not self.flight and self.press_on:
                outfield = [p for p in team if p.slot != 0]
                by_distance = sorted(outfield, key=lambda p: math.hypot(p.x - bx, p.y - by))
                if by_distance and math.hypot(by_distance[0].x - bx, by_distance[0].y - by) < 16:
                    presser = by_distance[0]
                    cover = by_distance[1] if len(by_distance) > 1 else None
            for p in team:
                role, sx, sy = formation[p.slot]
                if dead:
                    x, y = self._kickoff_spot(side, p.slot, kicking=self.restart[0] == side)  # type: ignore[index]
                    out[id(p)] = (x, y, 0.35)
                    continue
                if role == "gk":
                    gx = 4 + max(0.0, tbx - 31.5) * 0.1
                    gy = 34 + (tby - 34) * 0.15
                    x, y = self._from_team(side, gx, gy)
                    out[id(p)] = (x, y, 0.6)
                    continue
                fx = _clamp(47 + (sx - 47) * depth + advance, 2, 103)
                fy = _clamp(34 + (sy - 34) * width + lateral, 2, 66)
                urgency = 0.31 + 0.12 * p.player.work_rate
                # Attackers make intermittent runs in behind when their side has the ball.
                if in_possession and role in ("fwd", "mid") and tbx > 40:
                    phase = math.sin(self.t / (3_500 + p.slot * 450) + p.slot)
                    if phase > 0.6:
                        fx = min(fx + (10 if role == "fwd" else 6), 101)
                        urgency = 0.92
                x, y = self._from_team(side, fx, fy)
                if p is self.holder:
                    if self._blocked_ahead(p):
                        out[id(p)] = (p.x, p.y, 0.15)  # shield the ball
                    else:
                        gx, gy = self._to_team(side, p.x, p.y)
                        gx, gy = self._from_team(side, min(gx + 6, 103), gy + (34 - gy) * 0.2)
                        out[id(p)] = (gx, gy, 0.6)
                    continue
                if self.flight and p is self.flight.receiver:
                    out[id(p)] = (self.flight.x1, self.flight.y1, 0.95)
                    continue
                if p is presser:
                    out[id(p)] = (bx, by, 0.75 + 0.2 * p.player.work_rate)
                    continue
                if p is cover:
                    cx, cy = self._from_team(side, max(tbx - 6, 2), tby)
                    out[id(p)] = (cx, cy, 0.7)
                    continue
                out[id(p)] = (x, y, urgency)
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
            p.sprint_len += speed * TICK_MS / 1000
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
        if not h or self.flight or self.t < self.dead_until_ms:
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
