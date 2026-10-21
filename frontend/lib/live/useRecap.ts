"use client";

import { useEffect, useState } from "react";

import { getJson } from "@/lib/api";
import type { MatchRecap, Recap, YourDay } from "@/lib/contracts.generated";

type Status = Recap["status"];

// How often to ask: quickly while a writer is on it, slowly otherwise (the day ends, or loops).
const EVERY_MS: Record<Status, number> = {
  pending: 10_000,
  writing: 2_000,
  ready: 15_000,
};

/** Fetch `path` now and every so often, faster while `status` of the latest answer says so.
 * No path: nothing to fetch (null). */
function usePolled<T>(
  path: string | null,
  status: (value: T) => Status,
): T | null {
  const [held, setHeld] = useState<{ path: string; value: T } | null>(null);
  const value = held && held.path === path ? held.value : null;
  const current = value ? status(value) : "pending";
  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    const load = () =>
      getJson<T>(path)
        .then((v) => !cancelled && setHeld({ path, value: v }))
        .catch(() => undefined); // the backend is waking up or away: try again next time
    void load();
    const timer = setInterval(load, EVERY_MS[current]);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [path, current]);
  return value;
}

const query = (ended: boolean) => (ended ? "?ended=true" : "");

/** How the matchday unfolded (backend /api/recap): pending until its last match ends, unless
 * `ended` asks for the finished day whatever the clock says (the /recap page). */
export function useRecap(ended = false): Recap | null {
  return usePolled<Recap>(`/api/recap${query(ended)}`, (r) => r.status);
}

/** One match's recap, at its final whistle. */
export function useMatchRecap(
  matchId: string,
  ended = false,
): MatchRecap | null {
  return usePolled<MatchRecap>(
    `/api/matches/${matchId}/recap${query(ended)}`,
    (r) => r.status,
  );
}

/** Every match's recap, in fixture order: "writing" while any is still being written. */
export function useMatchRecaps(ended = false): MatchRecap[] | null {
  return usePolled<MatchRecap[]>(`/api/recaps${query(ended)}`, (all) =>
    all.some((r) => r.status === "writing")
      ? "writing"
      : all.every((r) => r.status === "ready")
        ? "ready"
        : "pending",
  );
}

/** A signed-in fan's own matchday, beside the recap (`lens` from lib/whip.ts); none for the
 * main channel. */
export function useYourDay(lens: string | null, ended = false): YourDay | null {
  const path = lens
    ? `/api/recap/yours?lens=${encodeURIComponent(lens)}${ended ? "&ended=true" : ""}`
    : null;
  return usePolled<YourDay>(path, (d) => d.status);
}
