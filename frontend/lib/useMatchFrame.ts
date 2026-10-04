"use client";

import { useEffect, useState } from "react";

import type { TrackingFrame } from "@/lib/contracts.generated";
import { frameAt } from "@/lib/matchSim";
import { MATCH } from "@/lib/mock";

const FRAME_MS = 1000 / 30;
const REDUCED_FRAME_MS = 250;

/**
 * The tracking frame at the current match clock, refreshed on animation frames (~30 fps, or 4 fps
 * when the viewer prefers reduced motion). Every view that calls this with the same clock shows
 * the same instant, which is what keeps the program camera and tactical view in sync.
 */
export function useMatchFrame(getClockMs: () => number): TrackingFrame {
  const [frame, setFrame] = useState(() => frameAt(MATCH.clockMs));

  useEffect(() => {
    const reduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const interval = reduced ? REDUCED_FRAME_MS : FRAME_MS;
    let raf = 0;
    let lastDraw = 0;
    const loop = (now: number) => {
      if (now - lastDraw >= interval) {
        lastDraw = now;
        setFrame(frameAt(getClockMs()));
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [getClockMs]);

  return frame;
}
