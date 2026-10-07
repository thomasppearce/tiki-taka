"use client";

import { useEffect, useMemo, useState } from "react";

import { getJson } from "@/lib/api";
import type { MatchEvent } from "@/lib/contracts.generated";

/**
 * The cited events this page doesn't have yet. The live stream only carries events from when
 * the page opened (plus the latest few), but a key moment or proposal can cite plays from much
 * earlier; those are fetched by id so their receipts can still be shown on the pitch.
 */
export function useEvidence(
  matchId: string,
  cited: readonly string[],
  known: readonly MatchEvent[],
): MatchEvent[] {
  // Several claims can cite the same event; each is fetched and drawn once.
  const ids = useMemo(() => [...new Set(cited)], [cited]);
  const [fetched, setFetched] = useState<ReadonlyMap<string, MatchEvent>>(
    new Map(),
  );
  const knownIds = useMemo(
    () => new Set(known.map((e) => e.event_id)),
    [known],
  );
  const missing = ids
    .filter((id) => !knownIds.has(id) && !fetched.has(id))
    .join(",");

  useEffect(() => {
    if (!missing) return;
    let cancelled = false;
    getJson<MatchEvent[]>(
      `/api/matches/${matchId}/events?ids=${encodeURIComponent(missing)}`,
    )
      .then((events) => {
        if (cancelled) return;
        setFetched((before) => {
          const next = new Map(before);
          for (const e of events) next.set(e.event_id, e);
          return next;
        });
      })
      .catch(() => undefined); // the receipts just won't show on the pitch
    return () => {
      cancelled = true;
    };
  }, [matchId, missing]);

  return useMemo(
    () =>
      ids
        .filter((id) => !knownIds.has(id))
        .map((id) => fetched.get(id))
        .filter((e): e is MatchEvent => e !== undefined)
        .sort((a, b) => a.match_clock_ms - b.match_clock_ms),
    [ids, knownIds, fetched],
  );
}
