import { useEffect, useState } from "react";

import type { MatchEvent } from "@/lib/contracts.generated";

export type StreamStatus = "connecting" | "live" | "reconnecting";

// Must be referenced literally so Next.js can inline it at build time.
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

const MAX_EVENTS = 50;

/** Subscribe to the backend's live match-event stream. Newest event first. */
export function useMatchEvents(): {
  events: MatchEvent[];
  status: StreamStatus;
} {
  const [events, setEvents] = useState<MatchEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>("connecting");

  useEffect(() => {
    const source = new EventSource(`${API_URL}/api/stream/events`);

    source.onopen = () => {
      setStatus("live");
      // Phase 0's fake stream restarts from kickoff on every reconnect, so start fresh.
      setEvents([]);
    };
    // EventSource reconnects on its own; we only reflect the state.
    source.onerror = () => setStatus("reconnecting");

    source.addEventListener("match_event", (message) => {
      // TypeScript types are compile-time only; the backend validates every event it sends.
      const event = JSON.parse(message.data) as MatchEvent;
      setEvents((previous) => [event, ...previous].slice(0, MAX_EVENTS));
    });

    return () => source.close();
  }, []);

  return { events, status };
}
