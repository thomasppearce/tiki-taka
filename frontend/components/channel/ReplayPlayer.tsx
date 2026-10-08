"use client";

import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";

import { LiveCamera } from "@/components/broadcast/LiveCamera";
import { cameraAim } from "@/components/control-room/ProgramMonitor";
import type { Replay } from "@/lib/contracts.generated";
import { FrameBuffer } from "@/lib/live/frameBuffer";
import type { FrameSource } from "@/lib/live/useLiveMatch";
import { DURATION, EASE } from "@/lib/motion";
import { useMatchFrame } from "@/lib/useMatchFrame";

/** Playback speed through the shot (the slow-motion window the backend marks). */
const SLOW_SPEED = 0.4;

/**
 * A replay of the move behind a goal or a big chance: the frames play on their own clock, in
 * real time through the build-up and in slow motion through the shot, with the shooter ringed.
 * The live stream keeps buffering underneath, so the feed returns to live when it ends.
 */
export function ReplayPlayer({
  replay,
  showLabel,
  onDone,
}: {
  replay: Replay;
  /** The cut banner already says what happened when a cut opens with the replay. */
  showLabel: boolean;
  onDone: () => void;
}) {
  const buffer = useMemo(() => {
    const b = new FrameBuffer();
    for (const frame of replay.frames) b.push(frame);
    return b;
  }, [replay]);
  const clock = useMemo(() => new ReplayClock(replay), [replay]);
  const [slow, setSlow] = useState(false);
  const source = useMemo<FrameSource>(
    () => ({
      getClockMs: () => clock.now(),
      frameAt: (ms) => buffer.at(ms),
      ballXAt: (ms) => buffer.ballXAt(ms),
    }),
    [buffer, clock],
  );
  const done = useRef(onDone);
  useEffect(() => {
    done.current = onDone;
  }, [onDone]);

  useEffect(() => {
    clock.start(performance.now());
    let raf = 0;
    let wasSlow = false;
    const tick = (now: number) => {
      const { finished, inSlow } = clock.advance(now);
      if (inSlow !== wasSlow) {
        wasSlow = inSlow;
        setSlow(inSlow);
      }
      if (finished) {
        done.current();
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [clock]);

  const frame = useMatchFrame(source);
  return (
    <>
      {frame && (
        <LiveCamera
          frame={frame}
          aimX={cameraAim(source, frame)}
          tag={null}
          focusPlayerId={replay.shooter_id}
        />
      )}
      <div className="absolute top-[3.5cqw] right-[3.5cqw] flex h-[4.4cqw] items-stretch font-broadcast text-[2.4cqw] leading-none font-semibold tracking-wider text-ink uppercase">
        <span className="flex items-center bg-air px-[1.3cqw] text-ink-on-fill">
          Replay
        </span>
        {slow && (
          <span className="flex items-center bg-page/95 px-[1.3cqw]">
            Slow motion
          </span>
        )}
      </div>
      {showLabel && (
        <motion.div
          className="absolute bottom-[4.5cqw] left-[3.5cqw] w-max max-w-[88cqw] font-broadcast text-ink"
          initial={{ clipPath: "inset(0 100% 0 0)" }}
          animate={{ clipPath: "inset(0 0% 0 0)" }}
          transition={{ duration: DURATION.verySlow, ease: EASE.smoothOut }}
        >
          <p className="flex text-[3.4cqw] leading-none font-bold uppercase">
            <span className="w-[0.7cqw] shrink-0 bg-air" />
            <span className="bg-page/95 px-[2.2cqw] py-[1.5cqw]">
              {replay.label}
            </span>
          </p>
          {replay.as_it_stands && (
            <p className="ml-[0.7cqw] bg-raised/95 px-[2.2cqw] py-[1.2cqw] text-[2.2cqw] leading-tight font-semibold text-ink-2">
              {replay.as_it_stands}
            </p>
          )}
        </motion.div>
      )}
    </>
  );
}

/** A replay's own clock: real time through the build-up, slow motion through the shot. */
class ReplayClock {
  private ms: number;
  private last = 0;

  constructor(private readonly replay: Replay) {
    this.ms = replay.from_ms;
  }

  now(): number {
    return this.ms;
  }

  start(wallMs: number): void {
    this.ms = this.replay.from_ms;
    this.last = wallMs;
  }

  advance(wallMs: number): { finished: boolean; inSlow: boolean } {
    const { slow_from_ms: from, slow_to_ms: to, to_ms: end } = this.replay;
    const inSlow = this.ms >= from && this.ms <= to;
    this.ms += (wallMs - this.last) * (inSlow ? SLOW_SPEED : 1);
    this.last = wallMs;
    return { finished: this.ms >= end, inSlow };
  }
}
