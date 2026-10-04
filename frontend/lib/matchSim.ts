/**
 * Stand-in for the backend generator's event + tracking stream (CLAUDE.md 5.7).
 *
 * Continues the mock match from 63:12: Westmere press, Northgate defend a lead. It generates
 * on-ball events (passes between real teammates, tackles, shots, saves) plus off-ball pressure,
 * and derives a TrackingFrame for any instant:
 * - The ball follows the events: it flies along each pass, then is carried by the receiver.
 * - Each team holds a formation that slides with the ball, compact without it, wider with it.
 * - The receiver runs onto the pass; the carrier stays on the ball.
 * Everything is a pure function of the match clock and a fixed seed, so every view (and every
 * refresh) sees the same match. The backend generator replaces this module.
 */

import type {
  MatchEvent,
  PlayerPosition,
  TrackingFrame,
} from "@/lib/contracts.generated";
import {
  MATCH,
  PLAYERS,
  RECENT_EVENTS,
  type TeamId,
  makeEvent,
} from "@/lib/mock";

type Point = { x: number; y: number };
type Role = "gk" | "def" | "mid" | "fwd";
type Slot = { id: string; x: number; y: number; role: Role };

/** Formations in each team's own attacking frame: x 0 = own goal, 100 = opponent goal. */
const SHAPES: Record<TeamId, Slot[]> = {
  t_home: [
    { id: "p_home_01", x: 5, y: 50, role: "gk" },
    { id: "p_home_02", x: 22, y: 86, role: "def" },
    { id: "p_home_04", x: 20, y: 62, role: "def" },
    { id: "p_home_05", x: 20, y: 38, role: "def" },
    { id: "p_home_03", x: 22, y: 14, role: "def" },
    { id: "p_home_07", x: 44, y: 86, role: "mid" },
    { id: "p_home_06", x: 40, y: 60, role: "mid" },
    { id: "p_home_08", x: 40, y: 40, role: "mid" },
    { id: "p_home_11", x: 44, y: 14, role: "mid" },
    { id: "p_home_09", x: 64, y: 58, role: "fwd" },
    { id: "p_home_10", x: 62, y: 40, role: "fwd" },
  ],
  t_away: [
    { id: "p_away_01", x: 5, y: 50, role: "gk" },
    { id: "p_away_02", x: 24, y: 86, role: "def" },
    { id: "p_away_05", x: 22, y: 62, role: "def" },
    { id: "p_away_04", x: 22, y: 38, role: "def" },
    { id: "p_away_03", x: 24, y: 14, role: "def" },
    { id: "p_away_06", x: 42, y: 50, role: "mid" },
    { id: "p_away_08", x: 46, y: 72, role: "mid" },
    { id: "p_away_10", x: 48, y: 30, role: "mid" },
    { id: "p_away_07", x: 68, y: 84, role: "fwd" },
    { id: "p_away_09", x: 72, y: 50, role: "fwd" },
    { id: "p_away_11", x: 68, y: 16, role: "fwd" },
  ],
};

const OTHER: Record<TeamId, TeamId> = { t_home: "t_away", t_away: "t_home" };
const PASS_SPEED_MPS = 16;
const SHAPE_BLEND_MS = 1_500;
const LOOKAHEAD_MS = 8_000;

/** Team behavior for this storyline: Westmere press and progress, Northgate struggle to hold it. */
const STYLE: Record<TeamId, { forward: number; success: number }> = {
  t_away: { forward: 1.0, success: 0.9 },
  t_home: { forward: 0.55, success: 0.78 },
};

// --- Frames of reference ---------------------------------------------------------------------

const toTeam = (team: TeamId, p: Point): Point =>
  team === "t_home" ? p : { x: 100 - p.x, y: 100 - p.y };
const fromTeam = toTeam; // the mirror is its own inverse

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const lerpPoint = (a: Point, b: Point, t: number): Point => ({
  x: lerp(a.x, b.x, t),
  y: lerp(a.y, b.y, t),
});
const clamp = (v: number, lo: number, hi: number) =>
  Math.min(hi, Math.max(lo, v));
const metres = (a: Point, b: Point) =>
  Math.hypot((a.x - b.x) * 1.05, (a.y - b.y) * 0.68);

/** Where a team's players stand for a given ball position (pitch coordinates). */
function shape(
  team: TeamId,
  ball: Point,
  inPossession: boolean,
): Map<string, Point> {
  const b = toTeam(team, ball);
  const advance = (b.x - 50) * (inPossession ? 0.55 : 0.45);
  const depth = inPossession ? 1.0 : 0.72;
  const width = inPossession ? 1.0 : 0.78;
  const lateral = (b.y - 50) * (inPossession ? 0.18 : 0.35);
  const out = new Map<string, Point>();
  for (const slot of SHAPES[team]) {
    const p =
      slot.role === "gk"
        ? { x: 4 + Math.max(0, b.x - 30) * 0.1, y: 50 + (b.y - 50) * 0.15 }
        : {
            x: clamp(45 + (slot.x - 45) * depth + advance, 3, 97),
            y: clamp(50 + (slot.y - 50) * width + lateral, 3, 97),
          };
    out.set(slot.id, fromTeam(team, p));
  }
  return out;
}

// --- Event generation (deterministic, cached) ---------------------------------------------------

/** An on-ball event's path: where the ball starts, where it ends, and when it gets there. */
type BallLeg = {
  event: MatchEvent;
  t: number;
  from: Point;
  to: Point;
  arriveMs: number;
  carrier: string;
  team: TeamId;
};

type Sim = {
  rand: () => number;
  t: number;
  team: TeamId;
  carrier: string;
  ball: Point;
  n: number;
};

const legs: BallLeg[] = [];
const offBall: MatchEvent[] = [];
const last = RECENT_EVENTS[RECENT_EVENTS.length - 1];
const sim: Sim = {
  rand: mulberry32(20261003),
  t: MATCH.clockMs + 600,
  team: "t_away",
  carrier: "p_away_09",
  ball: last.end_location ?? last.location ?? { x: 18, y: 38 },
  n: 619,
};

/** A MatchEvent stamped with the exact simulated time (makeEvent only resolves whole seconds). */
function simEvent(
  t: number,
  type: MatchEvent["type"],
  player: string,
  at: Point,
  to: Point | null = null,
  attributes: Partial<MatchEvent["attributes"]> = {},
): MatchEvent {
  const ev = makeEvent(
    sim.n++,
    clockText(t),
    type,
    player,
    [at.x, at.y],
    to ? [to.x, to.y] : null,
    attributes,
  );
  ev.match_clock_ms = Math.round(t);
  return ev;
}

function ensureUntil(clockMs: number) {
  while (sim.t < clockMs + LOOKAHEAD_MS) step();
}

function nearest(
  ids: Map<string, Point>,
  to: Point,
  exclude?: string,
): [string, Point] {
  let best: [string, Point] = ["", { x: 0, y: 0 }];
  let bestD = Infinity;
  for (const [id, p] of ids) {
    if (id === exclude) continue;
    const d = metres(p, to);
    if (d < bestD) [best, bestD] = [[id, p], d];
  }
  return best;
}

function step() {
  const r = sim.rand;
  const { team, carrier, ball } = sim;
  const opp = OTHER[team];
  const own = shape(team, ball, true);
  const theirs = shape(opp, ball, false);
  const b = toTeam(team, ball);
  const [presserId, presserAt] = nearest(theirs, ball);
  const pressure = clamp(1 - metres(presserAt, ball) / 12, 0, 1);

  // Off-ball: the nearest defender closes the carrier down.
  if (pressure > 0.35 && r() < 0.5) {
    offBall.push(
      simEvent(sim.t - 400, "pressure", presserId, presserAt, null, {
        pressure_level: round(pressure, 2),
      }),
    );
  }

  const roll = r();
  if (b.x > 74 && roll < 0.2) return shoot(theirs);
  if (roll < 0.07 + pressure * 0.08) return tackle(presserId);
  return pass(own, theirs, pressure);

  function shoot(oppShape: Map<string, Point>) {
    const goal = fromTeam(team, { x: 100, y: 50 + (r() - 0.5) * 10 });
    const outcome = r() < 0.5 ? "saved" : r() < 0.7 ? "off_target" : "blocked";
    const speed = round(68 + r() * 40, 1);
    const shot = simEvent(sim.t, "shot", carrier, ball, goal, {
      ball_speed_kmh: speed,
    });
    shot.outcome = outcome;
    const keeper = SHAPES[opp][0].id;
    const keeperAt = oppShape.get(keeper)!;
    const flight = (metres(ball, goal) / (speed / 3.6)) * 1000;
    legs.push({
      event: shot,
      t: sim.t,
      from: ball,
      to: keeperAt,
      arriveMs: sim.t + flight,
      carrier: keeper,
      team: opp,
    });
    sim.t += flight + 1_800;
    sim.team = opp;
    sim.carrier = keeper;
    sim.ball = keeperAt;
  }

  function tackle(winner: string) {
    const ev = simEvent(sim.t, "tackle", winner, ball);
    legs.push({
      event: ev,
      t: sim.t,
      from: ball,
      to: ball,
      arriveMs: sim.t,
      carrier: winner,
      team: opp,
    });
    sim.t += 900 + r() * 900;
    sim.team = opp;
    sim.carrier = winner;
    sim.ball = dribble(opp, ball);
  }

  function pass(
    ownShape: Map<string, Point>,
    oppShape: Map<string, Point>,
    pressureLevel: number,
  ) {
    const style = STYLE[team];
    const longBall = team === "t_home" && b.x < 30 && r() < 0.3;
    let best: [string, Point] | null = null;
    let bestScore = -Infinity;
    for (const [id, p] of ownShape) {
      if (id === carrier || (SHAPES[team][0].id === id && b.x > 25)) continue;
      const d = metres(ball, p);
      if (d < 6 || d > (longBall ? 55 : 38)) continue;
      const gain = toTeam(team, p).x - b.x;
      const score =
        gain * style.forward * (longBall ? 2 : 1) - d * 0.12 + r() * 9;
      if (score > bestScore) [best, bestScore] = [[id, p], score];
    }
    if (!best) best = nearest(ownShape, ball, carrier);
    const [target, targetAt] = best;
    const to = {
      x: clamp(targetAt.x + (r() - 0.5) * 3, 1, 99),
      y: clamp(targetAt.y + (r() - 0.5) * 3, 1, 99),
    };
    const distance = metres(ball, to);
    const difficulty = clamp(
      distance / 45 + pressureLevel * 0.35 + (r() - 0.5) * 0.2,
      0.05,
      0.98,
    );
    const success =
      r() < style.success - difficulty * 0.3 - (longBall ? 0.3 : 0);
    const ev = simEvent(sim.t, "pass", carrier, ball, to, {
      pass_distance_m: round(distance, 1),
      pass_difficulty: round(difficulty, 2),
      ball_speed_kmh: round(PASS_SPEED_MPS * 3.6 * (0.85 + r() * 0.3), 1),
      pressure_level: round(pressureLevel, 2),
    });
    ev.target_player_id = target;
    ev.outcome = success ? "success" : "fail";
    const flight = (distance / PASS_SPEED_MPS) * 1000;
    const [receiver, receiverTeam] = success
      ? [target, team]
      : [nearest(oppShape, to)[0], opp];
    legs.push({
      event: ev,
      t: sim.t,
      from: ball,
      to,
      arriveMs: sim.t + flight,
      carrier: receiver,
      team: receiverTeam,
    });
    sim.t += flight + 700 + r() * 1_100;
    sim.team = receiverTeam;
    sim.carrier = receiver;
    sim.ball = dribble(receiverTeam, to);
  }

  function dribble(byTeam: TeamId, from: Point): Point {
    const f = toTeam(byTeam, from);
    return fromTeam(byTeam, {
      x: clamp(f.x + 1.5 + r() * 4, 2, 98),
      y: clamp(f.y + (r() - 0.5) * 5, 2, 98),
    });
  }
}

// --- Queries ---------------------------------------------------------------------------------

/** Events up to the clock, oldest first: the mock history, then the simulated match. */
export function eventsUntil(clockMs: number): MatchEvent[] {
  ensureUntil(clockMs);
  const simulated = [...legs.map((l) => l.event), ...offBall].filter(
    (e) => e.match_clock_ms <= clockMs,
  );
  return [
    ...RECENT_EVENTS,
    ...simulated.sort((a, b) => a.match_clock_ms - b.match_clock_ms),
  ];
}

/** Ball, possession, carrier, and receiver at an instant. */
function ballState(clockMs: number) {
  ensureUntil(clockMs);
  let i = -1;
  while (i + 1 < legs.length && legs[i + 1].t <= clockMs) i++;
  if (i < 0) {
    const first = legs[0];
    return {
      ball: lerpPoint(
        sim0Ball,
        first.from,
        progress(MATCH.clockMs, first.t, clockMs),
      ),
      team: "t_away" as TeamId,
      carrier: "p_away_09",
      receiver: null,
      sinceChange: Infinity,
    };
  }
  const leg = legs[i];
  const next = legs[i + 1];
  const inFlight = clockMs < leg.arriveMs;
  const ball = inFlight
    ? lerpPoint(
        leg.from,
        leg.to,
        easeOut(progress(leg.t, leg.arriveMs, clockMs)),
      )
    : lerpPoint(leg.to, next.from, progress(leg.arriveMs, next.t, clockMs));
  const changedAt = lastPossessionChange(i);
  return {
    ball,
    team: leg.team,
    carrier: inFlight ? null : leg.carrier,
    receiver: inFlight ? leg.carrier : null,
    sinceChange: clockMs - changedAt,
  };
}

const sim0Ball = { ...sim.ball };

function lastPossessionChange(i: number): number {
  for (let k = i; k > 0; k--)
    if (legs[k].team !== legs[k - 1].team) return legs[k].arriveMs;
  return -Infinity;
}

/** Every player and the ball at an instant. */
export function frameAt(clockMs: number): TrackingFrame {
  const { ball, team, carrier, receiver, sinceChange } = ballState(clockMs);
  const blend = clamp(sinceChange / SHAPE_BLEND_MS, 0, 1);
  const players: PlayerPosition[] = [];
  const flight = receiver
    ? legs.find(
        (l) => l.carrier === receiver && l.t <= clockMs && clockMs < l.arriveMs,
      )
    : null;
  for (const side of ["t_home", "t_away"] as TeamId[]) {
    const attacking = side === team;
    const now = shape(side, ball, attacking);
    const before = shape(side, ball, !attacking);
    for (const slot of SHAPES[side]) {
      let p = lerpPoint(before.get(slot.id)!, now.get(slot.id)!, blend);
      if (slot.id === carrier)
        p = { x: ball.x - (side === "t_home" ? 0.8 : -0.8), y: ball.y };
      if (slot.id === receiver && flight) {
        p = lerpPoint(
          p,
          flight.to,
          easeOut(progress(flight.t, flight.arriveMs, clockMs)),
        );
      }
      const wobble =
        PLAYERS[slot.id].number * 1.7 + (side === "t_away" ? 0.9 : 0);
      players.push({
        player_id: slot.id,
        team_id: side,
        x: p.x + Math.sin(clockMs / 1_300 + wobble) * 0.5,
        y: p.y + Math.cos(clockMs / 1_700 + wobble) * 0.5,
        speed_kmh: null,
      });
    }
  }
  return {
    match_id: "m_demo",
    match_clock_ms: Math.round(clockMs),
    ball,
    // Always all 22 players, so the contract's non-empty list holds.
    players: players as TrackingFrame["players"],
  };
}

// --- Utilities -------------------------------------------------------------------------------

function progress(start: number, end: number, now: number): number {
  return end <= start ? 1 : clamp((now - start) / (end - start), 0, 1);
}

function easeOut(t: number): number {
  return 1 - (1 - t) ** 2;
}

function round(v: number, digits: number): number {
  const f = 10 ** digits;
  return Math.round(v * f) / f;
}

function clockText(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function mulberry32(seed: number): () => number {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** The ball's position at an instant. */
export function ballAt(clockMs: number): Point {
  return ballState(clockMs).ball;
}

/**
 * Where the main camera aims (pitch x, normalized): the ball's average position over the last
 * two seconds, so the camera follows play smoothly instead of snapping to every pass.
 */
export function cameraTargetAt(clockMs: number): number {
  let sum = 0;
  const samples = 10;
  for (let k = 0; k < samples; k++) sum += ballAt(clockMs - k * 200).x;
  return sum / samples;
}
