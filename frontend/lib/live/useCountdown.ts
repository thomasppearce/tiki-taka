"use client";

import { useEffect, useState } from "react";

const TICK_MS = 200;

const secondsLeft = (targetMs: number, nowMs: number) =>
  Math.max(0, Math.ceil((targetMs - nowMs) / 1000));

/** Whole seconds until `targetMs` on the server's matchday clock, refreshed five times a second. */
export function useCountdown(
  targetMs: number,
  serverClockMs: () => number,
): number {
  const [seconds, setSeconds] = useState(() =>
    secondsLeft(targetMs, serverClockMs()),
  );
  useEffect(() => {
    const timer = setInterval(
      () => setSeconds(secondsLeft(targetMs, serverClockMs())),
      TICK_MS,
    );
    return () => clearInterval(timer);
  }, [targetMs, serverClockMs]);
  return seconds;
}
