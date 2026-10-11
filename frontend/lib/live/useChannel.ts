"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { API_URL, getJson, postJson } from "@/lib/api";
import type {
  Channel,
  LeagueTable,
  Lens,
  MatchSignal,
} from "@/lib/contracts.generated";
import type { LiveStatus } from "@/lib/live/useLiveMatch";

export type ChannelControls = {
  /** Take the pending cut now, or cut straight to a match. */
  take: (matchId?: string) => Promise<void>;
  hold: (held: boolean) => Promise<void>;
  pin: (matchId: string | null) => Promise<void>;
};

export type LiveChannel = {
  status: LiveStatus;
  channel: Channel | null;
  signals: MatchSignal[];
  table: LeagueTable | null;
  /** The server's matchday clock now, extrapolated from the last snapshot (for countdowns). */
  serverClockMs: () => number;
  controls: ChannelControls;
};

/**
 * The whip-around, live: the channel (what's on air, the Director's next cut), every match's
 * signals (every 2 s), and the table as it stands (every 5 s), from one SSE stream. The match on
 * air is followed through its own stream (useLiveMatch) by whoever renders it.
 *
 * `lens` picks whose whip-around: null for the main channel, or a signed-in fan's own (their
 * club or their fantasy XI, see lib/whip.ts), whose XI points also arrive every 2 s.
 */
export function useChannel(lens: string | null = null): LiveChannel {
  const query = lens ? `?lens=${encodeURIComponent(lens)}` : "";
  // Snapshots are kept with the whip-around they belong to: after a switch, the old one reads
  // as nothing yet (another Director's versions aren't comparable).
  const [held, setHeld] = useState<{ query: string; channel: Channel } | null>(
    null,
  );
  const [signals, setSignals] = useState<MatchSignal[]>([]);
  const [table, setTable] = useState<LeagueTable | null>(null);
  const [statusOf, setStatusOf] = useState<{
    query: string;
    status: LiveStatus;
  }>({ query, status: "connecting" });
  const synced = useRef({ clockMs: 0, at: 0 });
  const channel = held?.query === query ? held.channel : null;
  const status = statusOf.query === query ? statusOf.status : "connecting";

  const setChannel = useCallback(
    (next: Channel) => {
      synced.current = { clockMs: next.clock_ms, at: performance.now() };
      // A response can race the stream: keep the newer snapshot unless the day started over.
      setHeld((current) =>
        current?.query === query &&
        next.version < current.channel.version &&
        next.clock_ms >= current.channel.clock_ms
          ? current
          : { query, channel: next },
      );
      setSignals(next.signals);
    },
    [query],
  );

  useEffect(() => {
    let cancelled = false;
    const setStatus = (status: LiveStatus | ((s: LiveStatus) => LiveStatus)) =>
      setStatusOf((current) => ({
        query,
        status: typeof status === "function" ? status(current.status) : status,
      }));
    getJson<Channel>(`/api/channel${query}`)
      .then((c) => !cancelled && setChannel(c))
      .catch(() => !cancelled && setStatus("offline"));
    const source = new EventSource(`${API_URL}/api/channel/stream${query}`);
    source.onerror = () =>
      setStatus((s) => (s === "live" ? "reconnecting" : "offline"));
    source.addEventListener("channel", (e) => {
      setChannel(JSON.parse((e as MessageEvent<string>).data) as Channel);
      setStatus("live");
    });
    source.addEventListener("signals", (e) => {
      setSignals(JSON.parse((e as MessageEvent<string>).data) as MatchSignal[]);
    });
    source.addEventListener("lens", (e) => {
      const next = JSON.parse((e as MessageEvent<string>).data) as Lens;
      setHeld((current) =>
        current?.query === query
          ? { query, channel: { ...current.channel, lens: next } }
          : current,
      );
    });
    source.addEventListener("table", (e) => {
      const next = JSON.parse((e as MessageEvent<string>).data) as LeagueTable;
      synced.current = { clockMs: next.clock_ms, at: performance.now() };
      setTable(next);
      setStatus("live");
    });
    return () => {
      cancelled = true;
      source.close();
    };
  }, [setChannel, query]);

  const serverClockMs = useCallback(
    () => synced.current.clockMs + (performance.now() - synced.current.at),
    [],
  );

  const send = useCallback(
    (path: string, body: unknown) =>
      postJson<Channel>(`${path}${query}`, body)
        .then(setChannel)
        .catch(() => undefined),
    [setChannel, query],
  );

  const controls: ChannelControls = {
    take: (matchId) => send("/api/channel/take", { match_id: matchId ?? null }),
    hold: (held) => send("/api/channel/hold", { held }),
    pin: (matchId) => send("/api/channel/pin", { match_id: matchId }),
  };

  return { status, channel, signals, table, serverClockMs, controls };
}
