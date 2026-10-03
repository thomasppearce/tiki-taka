"use client";

import type { MatchEvent } from "@/lib/contracts.generated";
import {
  API_URL,
  type StreamStatus,
  useMatchEvents,
} from "@/lib/useMatchEvents";

const STATUS_LABEL: Record<StreamStatus, string> = {
  connecting: "Connecting",
  live: "Live",
  reconnecting: "Reconnecting",
};

const STATUS_DOT: Record<StreamStatus, string> = {
  connecting: "bg-zinc-500",
  live: "bg-emerald-400",
  reconnecting: "bg-amber-400",
};

/** Phase 0 walking skeleton: the raw event stream as a list. */
export function EventFeed() {
  const { events, status } = useMatchEvents();

  return (
    <section className="flex w-full max-w-3xl flex-col gap-4">
      <header className="flex items-center justify-between">
        <h2 className="text-sm font-medium tracking-wide text-zinc-400 uppercase">
          Event stream
        </h2>
        <p
          role="status"
          className="flex items-center gap-2 text-sm text-zinc-300"
        >
          <span
            className={`size-2 rounded-full ${STATUS_DOT[status]}`}
            aria-hidden
          />
          {STATUS_LABEL[status]}
        </p>
      </header>

      {events.length === 0 ? (
        <EmptyState status={status} />
      ) : (
        <ol className="divide-y divide-zinc-800 rounded-lg border border-zinc-800">
          {events.map((event) => (
            <EventRow key={event.event_id} event={event} />
          ))}
        </ol>
      )}
    </section>
  );
}

function EmptyState({ status }: { status: StreamStatus }) {
  return (
    <div className="rounded-lg border border-dashed border-zinc-800 p-8 text-center text-sm text-zinc-400">
      {status === "reconnecting" ? (
        <>
          Can&apos;t reach the stream. Is the backend running at{" "}
          <code className="font-mono text-zinc-300">{API_URL}</code>?
        </>
      ) : (
        "Waiting for kickoff…"
      )}
    </div>
  );
}

function EventRow({ event }: { event: MatchEvent }) {
  return (
    <li className="grid grid-cols-[4rem_9rem_1fr] items-baseline gap-4 px-4 py-2.5 text-sm">
      <span className="font-mono text-zinc-400 tabular-nums">
        {formatClock(event)}
      </span>
      <span className="font-medium text-zinc-100">
        {formatType(event.type)}
      </span>
      <span className="truncate text-zinc-400">
        {[event.player_id, describeAttributes(event)]
          .filter(Boolean)
          .join(" · ")}
      </span>
    </li>
  );
}

function formatClock({ minute, second }: MatchEvent): string {
  return `${String(minute).padStart(2, "0")}:${String(second).padStart(2, "0")}`;
}

function formatType(type: MatchEvent["type"]): string {
  const label = type.replaceAll("_", " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function describeAttributes({ type, attributes: a }: MatchEvent): string {
  switch (type) {
    case "pass":
      return `${a.pass_distance_m} m, difficulty ${Math.round((a.pass_difficulty ?? 0) * 100)}`;
    case "shot":
      return `${a.ball_speed_kmh} km/h`;
    case "sprint":
      return `${a.top_speed_kmh} km/h over ${a.sprint_distance_m} m`;
    case "pressure":
      return `pressure ${Math.round((a.pressure_level ?? 0) * 100)}%`;
    default:
      return "";
  }
}
