"use client";

import { useEffect, useState } from "react";

import { getJson } from "@/lib/api";
import type { Recap } from "@/lib/contracts.generated";

// How often to ask: quickly while the writer is on it, slowly otherwise (the day ends, or loops).
const EVERY_MS: Record<Recap["status"], number> = {
  pending: 10_000,
  writing: 2_000,
  ready: 15_000,
};

/** How the final day unfolded (backend /api/recap): pending until the last match ends. */
export function useRecap(): Recap | null {
  const [recap, setRecap] = useState<Recap | null>(null);
  const status = recap?.status ?? "pending";
  useEffect(() => {
    let cancelled = false;
    const load = () =>
      getJson<Recap>("/api/recap")
        .then((r) => !cancelled && setRecap(r))
        .catch(() => undefined); // the backend is waking up or away: try again next time
    void load();
    const timer = setInterval(load, EVERY_MS[status]);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [status]);
  return recap;
}
