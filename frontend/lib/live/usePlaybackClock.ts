"use client";

import { useEffect, useState } from "react";

const TICK_MS = 250;

/** The playback clock as React state, refreshed at 4 Hz for clocks, queues, and timelines. */
export function usePlaybackClock(getClockMs: () => number): number {
  const [clockMs, setClockMs] = useState(getClockMs);
  useEffect(() => {
    const timer = setInterval(() => setClockMs(getClockMs()), TICK_MS);
    return () => clearInterval(timer);
  }, [getClockMs]);
  return clockMs;
}
