"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { API_URL, getJson, postJson } from "@/lib/api";
import type {
  Channel,
  LeagueTable,
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
 */
export function useChannel(): LiveChannel {
  const [channel, setChannelState] = useState<Channel | null>(null);
  const [signals, setSignals] = useState<MatchSignal[]>([]);
  const [table, setTable] = useState<LeagueTable | null>(null);
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const synced = useRef({ clockMs: 0, at: 0 });

  const setChannel = useCallback((next: Channel) => {
    synced.current = { clockMs: next.clock_ms, at: performance.now() };
    // A response can race the stream: keep the newer snapshot unless the day started over.
    setChannelState((current) =>
      current &&
      next.version < current.version &&
      next.clock_ms >= current.clock_ms
        ? current
        : next,
    );
    setSignals(next.signals);
  }, []);

  useEffect(() => {
    let cancelled = false;
    getJson<Channel>("/api/channel")
      .then((c) => !cancelled && setChannel(c))
      .catch(() => !cancelled && setStatus("offline"));
    const source = new EventSource(`${API_URL}/api/channel/stream`);
    source.onerror = () =>
      setStatus((s) => (s === "live" ? "reconnecting" : "offline"));
    source.addEventListener("channel", (e) => {
      setChannel(JSON.parse((e as MessageEvent<string>).data) as Channel);
      setStatus("live");
    });
    source.addEventListener("signals", (e) => {
      setSignals(JSON.parse((e as MessageEvent<string>).data) as MatchSignal[]);
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
  }, [setChannel]);

  const serverClockMs = useCallback(
    () => synced.current.clockMs + (performance.now() - synced.current.at),
    [],
  );

  const send = useCallback(
    (path: string, body: unknown) =>
      postJson<Channel>(path, body)
        .then(setChannel)
        .catch(() => undefined),
    [setChannel],
  );

  const controls: ChannelControls = {
    take: (matchId) => send("/api/channel/take", { match_id: matchId ?? null }),
    hold: (held) => send("/api/channel/hold", { held }),
    pin: (matchId) => send("/api/channel/pin", { match_id: matchId }),
  };

  return { status, channel, signals, table, serverClockMs, controls };
}
