"use client";

import { useEffect, useState } from "react";

import { getJson } from "@/lib/api";
import type { MatchRecap, Recap } from "@/lib/contracts.generated";

type Status = Recap["status"];

// How often to ask: quickly while a writer is on it, slowly otherwise (the day ends, or loops).
const EVERY_MS: Record<Status, number> = {
  pending: 10_000,
  writing: 2_000,
  ready: 15_000,
};

/** Fetch `path` now and every so often, faster while `status` of the latest answer says so. */
function usePolled<T>(path: string, status: (value: T) => Status): T | null {
  const [value, setValue] = useState<T | null>(null);
  const current = value ? status(value) : "pending";
  useEffect(() => {
    let cancelled = false;
    const load = () =>
      getJson<T>(path)
        .then((v) => !cancelled && setValue(v))
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
