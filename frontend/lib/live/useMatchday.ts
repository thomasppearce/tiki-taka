"use client";

import { useEffect, useState } from "react";

import { getJson } from "@/lib/api";
import type { Matchday } from "@/lib/contracts.generated";

const POLL_MS = 5_000;

export type MatchdayStatus = "loading" | "live" | "offline";

/** The match centre: every fixture's card, refreshed every few seconds. */
export function useMatchday(): {
  matchday: Matchday | null;
  status: MatchdayStatus;
} {
  const [matchday, setMatchday] = useState<Matchday | null>(null);
  const [status, setStatus] = useState<MatchdayStatus>("loading");

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      getJson<Matchday>("/api/matchday")
        .then((day) => {
          if (cancelled) return;
          setMatchday(day);
          setStatus("live");
        })
        .catch(() => {
          if (!cancelled) setStatus("offline");
        });
    void load();
    const timer = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return { matchday, status };
}
