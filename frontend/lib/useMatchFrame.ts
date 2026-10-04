"use client";

import { useEffect, useState } from "react";

import type { TrackingFrame } from "@/lib/contracts.generated";
import type { FrameSource } from "@/lib/live/useLiveMatch";

const FRAME_MS = 1000 / 30;
const REDUCED_FRAME_MS = 250;

/**
 * The tracking frame at the playback clock, refreshed on animation frames (~30 fps, or 4 fps
 * when the viewer prefers reduced motion). Every view that reads the same source shows the same
 * instant, which is what keeps the program camera and the tactical view in sync. Null until the
 * first frame arrives.
 */
export function useMatchFrame(source: FrameSource): TrackingFrame | null {
  const [frame, setFrame] = useState(() => source.frameAt(source.getClockMs()));

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
        setFrame(source.frameAt(source.getClockMs()));
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [source]);

  return frame;
}
