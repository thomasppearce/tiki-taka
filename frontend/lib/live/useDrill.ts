"use client";

import { useCallback, useEffect, useState } from "react";

import { getJson, postJson } from "@/lib/api";
import type { DrillRequest, DrillState } from "@/lib/contracts.generated";

const POLL_MS = 2_000; // while a drill runs: a blip ends when the agent next calls

/**
 * The failure drill (backend app/agents/drill.py): which agent is failing on purpose, with
 * start and end. Polls only while a drill runs, so its countdown and a blip's end show up.
 */
export function useDrill() {
  const [drill, setDrill] = useState<DrillState | null>(null);
  const [busy, setBusy] = useState(false);

  const active = drill?.agent != null;
  useEffect(() => {
    let cancelled = false;
    const load = () =>
      getJson<DrillState>("/api/drill")
        .then((state) => !cancelled && setDrill(state))
        .catch(() => undefined); // the backend is waking up or away: keep what we had
    void load();
    const timer = active ? setInterval(load, POLL_MS) : undefined;
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [active]);

  const send = useCallback(
    async (path: string, body: DrillRequest | object) => {
      setBusy(true);
      try {
        setDrill(await postJson<DrillState>(path, body));
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  return {
    drill,
    busy,
    start: (request: DrillRequest) => send("/api/drill", request),
    end: () => send("/api/drill/end", {}),
  };
}
