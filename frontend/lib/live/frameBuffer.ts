/**
 * Smooth playback of the backend's tracking stream.
 *
 * The server sends a TrackingFrame about every 250 ms. The browser draws at ~30 fps, a little
 * behind the newest frame (PLAYOUT_DELAY_MS), so there is always a frame on each side of the
 * instant being drawn: players follow a Catmull-Rom curve through the frames (smooth position
 * and speed, no corners every quarter second), and the ball moves in straight lines, as it does.
 * Nothing is ever extrapolated, so nobody can overshoot and snap back.
 */

import type { PlayerPosition, TrackingFrame } from "@/lib/contracts.generated";

/** How far behind the newest frame playback runs: one frame interval plus network jitter. */
export const PLAYOUT_DELAY_MS = 700;
/** A clock change bigger than this is a cut (the matchday looped, or the server restarted). */
const JUMP_MS = 5_000;
/** How much history to keep (the camera averages the last two seconds of ball position). */
const KEEP_MS = 15_000;
/** How quickly the clock estimate forgets a lucky, low-latency frame (ms per frame). */
const DRIFT_PER_FRAME_MS = 2;

type Indexed = {
  frame: TrackingFrame;
  players: Map<string, PlayerPosition>;
};

export class FrameBuffer {
  private frames: Indexed[] = [];

  clear(): void {
    this.frames = [];
  }

  get size(): number {
    return this.frames.length;
  }

  push(frame: TrackingFrame): void {
    const last = this.frames.at(-1);
    if (last && frame.match_clock_ms <= last.frame.match_clock_ms) {
      if (frame.match_clock_ms > last.frame.match_clock_ms - JUMP_MS) return; // stale duplicate
      this.clear(); // the clock went back: a new matchday loop
    }
    this.frames.push({
      frame,
      players: new Map(frame.players.map((p) => [p.player_id, p])),
    });
    const oldest = frame.match_clock_ms - KEEP_MS;
    while (
      this.frames.length > 4 &&
      this.frames[0].frame.match_clock_ms < oldest
    )
      this.frames.shift();
  }

  /** Everyone and the ball at `clockMs`, interpolated; held at the ends of the buffer. */
  at(clockMs: number): TrackingFrame | null {
    const span = this.bracket(clockMs);
    if (!span) return null;
    const { i, f } = span;
    const n = this.frames.length;
    const p0 = this.frames[Math.max(i - 1, 0)];
    const p1 = this.frames[i];
    const p2 = this.frames[Math.min(i + 1, n - 1)];
    const p3 = this.frames[Math.min(i + 2, n - 1)];
    // Players present in the frame ahead; a substitute takes over his slot's position.
    const players = p2.frame.players.map((b) => {
      const a = p1.players.get(b.player_id) ?? b;
      const z = p0.players.get(b.player_id) ?? a;
      const c = p3.players.get(b.player_id) ?? b;
      return {
        ...b,
        x: catmullRom(z.x, a.x, b.x, c.x, f),
        y: catmullRom(z.y, a.y, b.y, c.y, f),
        speed_kmh:
          a.speed_kmh === null || b.speed_kmh === null
            ? b.speed_kmh
            : a.speed_kmh + (b.speed_kmh - a.speed_kmh) * f,
      };
    });
    return {
      match_id: p2.frame.match_id,
      match_clock_ms: Math.round(clockMs),
      ball: {
        x: lerp(p1.frame.ball.x, p2.frame.ball.x, f),
        y: lerp(p1.frame.ball.y, p2.frame.ball.y, f),
      },
      // Mapped one-to-one from a frame's (non-empty) player list, so still non-empty.
      players: players as TrackingFrame["players"],
    };
  }

  /** The ball's x (0-100) at `clockMs`, for the camera. */
  ballXAt(clockMs: number): number | null {
    const span = this.bracket(clockMs);
    if (!span) return null;
    const a = this.frames[span.i].frame.ball.x;
    const b =
      this.frames[Math.min(span.i + 1, this.frames.length - 1)].frame.ball.x;
    return lerp(a, b, span.f);
  }

  /** The frame at or before `clockMs` and how far toward the next one it is. */
  private bracket(clockMs: number): { i: number; f: number } | null {
    const n = this.frames.length;
    if (!n) return null;
    if (clockMs <= this.frames[0].frame.match_clock_ms) return { i: 0, f: 0 };
    if (clockMs >= this.frames[n - 1].frame.match_clock_ms)
      return { i: n - 1, f: 0 };
    let lo = 0;
    let hi = n - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (this.frames[mid].frame.match_clock_ms <= clockMs) lo = mid;
      else hi = mid;
    }
    const t0 = this.frames[lo].frame.match_clock_ms;
    const t1 = this.frames[hi].frame.match_clock_ms;
    return { i: lo, f: (clockMs - t0) / (t1 - t0) };
  }
}

/**
 * The playback clock: the server's match clock, as seen through the stream, minus the playout
 * delay. Frames are stamped with the server's clock when sent; the frame that arrived with the
 * least delay pins the estimate (the rest only arrived later), and it forgets slowly so clock
 * drift is followed. Reads from `performance.now()`, so it advances smoothly between frames.
 */
export class PlaybackClock {
  private offset: number | null = null;
  private newest: number | null = null;

  /** Note a frame's clock as it arrives. Returns true if the match clock jumped (a cut). */
  observe(clockMs: number, arrivedAt: number = performance.now()): boolean {
    // After the final whistle the server's clock holds, so every frame repeats it: hold with
    // it, rather than run on and take the gap for a cut (which replayed the last seconds).
    if (clockMs === this.newest) return false;
    this.newest = clockMs;
    const offset = clockMs - arrivedAt;
    if (this.offset === null) {
      this.offset = offset;
      return false;
    }
    if (Math.abs(offset - this.offset) > JUMP_MS) {
      this.offset = offset;
      return true;
    }
    this.offset = Math.max(offset, this.offset - DRIFT_PER_FRAME_MS);
    return false;
  }

  /** The match clock being drawn now, or null before the first frame: never past the newest
   * frame, so a finished match holds its last picture. */
  now(at: number = performance.now()): number | null {
    if (this.offset === null || this.newest === null) return null;
    return Math.min(at + this.offset - PLAYOUT_DELAY_MS, this.newest);
  }
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function catmullRom(p0: number, p1: number, p2: number, p3: number, t: number) {
  const t2 = t * t;
  return (
    0.5 *
    (2 * p1 +
      (p2 - p0) * t +
      (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
      (3 * p1 - p0 - 3 * p2 + p3) * t2 * t)
  );
}
