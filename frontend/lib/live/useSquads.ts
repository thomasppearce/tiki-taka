"use client";

import { useEffect, useState } from "react";

import { getJson } from "@/lib/api";
import type { Squads } from "@/lib/contracts.generated";

let request: Promise<Squads> | null = null;

/** Every player in the league, the team of the season, and the fantasy rules: fetched once. */
export function useSquads(): Squads | null {
  const [squads, setSquads] = useState<Squads | null>(null);
  useEffect(() => {
    let cancelled = false;
    request ??= getJson<Squads>("/api/squads").catch((error: unknown) => {
      request = null; // let the next mount try again
      throw error;
    });
    request.then((s) => !cancelled && setSquads(s)).catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);
  return squads;
}
