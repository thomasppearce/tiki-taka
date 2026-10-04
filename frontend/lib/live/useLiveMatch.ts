"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { API_URL, getJson } from "@/lib/api";
import type {
  AuditRecord,
  Desk,
  LiveEvent,
  MatchCard,
  MatchDetail,
  MatchEvent,
  TrackingFrame,
} from "@/lib/contracts.generated";
import { FrameBuffer, PlaybackClock } from "@/lib/live/frameBuffer";
import { type MatchInfo, matchInfo } from "@/lib/match";

export type LiveStatus = "connecting" | "live" | "reconnecting" | "offline";

/** What the animated views draw from: the playback clock, and the match at any instant on it. */
export type FrameSource = {
  getClockMs: () => number;
  frameAt: (clockMs: number) => TrackingFrame | null;
  ballXAt: (clockMs: number) => number | null;
};

export type LiveMatch = {
  status: LiveStatus;
  info: MatchInfo | null;
  source: FrameSource;
  /** The score when the detail loaded; goals after `clockMs` are counted from `events`. */
  baseline: { clockMs: number; home: number; away: number } | null;
  card: MatchCard | null;
  /** Every event known so far, oldest first; the newest may be just ahead of playback. */
  events: MatchEvent[];
  desk: Desk | null;
  /** Every audit record seen this session (the desk itself only keeps the latest 60). */
  history: AuditRecord[];
  setDesk: (desk: Desk) => void;
  refreshDesk: () => Promise<void>;
};

const MAX_EVENTS = 400;
const MAX_HISTORY = 600;
const RESTART_MS = 5_000;

/**
 * One match, live from the backend: the match detail (clubs, squads, score, recent events), then
 * the SSE stream (`frame` 4 Hz, `match_event`, `card` every 2 s, `desk` on change). Frames go
 * into a buffer the views sample on every animation frame; everything else is React state. If the
 * match clock jumps (the matchday looped, or the server restarted), it starts over cleanly.
 */
export function useLiveMatch(matchId: string): LiveMatch {
  const buffer = useRef(new FrameBuffer());
  const clock = useRef(new PlaybackClock());
  const fallbackClock = useRef(0);
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [card, setCard] = useState<MatchCard | null>(null);
  const [events, setEvents] = useState<MatchEvent[]>([]);
  const [desk, setDeskState] = useState<Desk | null>(null);
  const [history, setHistory] = useState<AuditRecord[]>([]);
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const [reloads, setReloads] = useState(0);

  const setDesk = useCallback((next: Desk) => {
    // A snapshot can arrive after a newer one (an approval's response races the stream); keep
    // the newer, unless the clock went back, which means the desk started over.
    setDeskState((current) =>
      current &&
      next.version < current.version &&
      next.clock_ms > current.clock_ms - RESTART_MS
        ? current
        : next,
    );
    setHistory((seen) => mergeAudit(next.audit, seen));
  }, []);

  const refreshDesk = useCallback(
    () =>
      getJson<Desk>(`/api/matches/${matchId}/desk`)
        .then(setDesk)
        .catch(() => undefined),
    [matchId, setDesk],
  );

  // The detail: loaded on mount and again whenever the stream (re)connects or cuts.
  useEffect(() => {
    let cancelled = false;
    getJson<MatchDetail>(`/api/matches/${matchId}`)
      .then((d) => {
        if (cancelled) return;
        fallbackClock.current = d.card.clock_ms;
        setDetail(d);
        setCard(d.card);
        setEvents((known) => mergeEvents(d.recent_events, known));
      })
      .catch(() => {
        if (!cancelled) setStatus((s) => (s === "live" ? s : "offline"));
      });
    return () => {
      cancelled = true;
    };
  }, [matchId, reloads]);

  useEffect(() => {
    const source = new EventSource(`${API_URL}/api/matches/${matchId}/stream`);
    let opened = false;
    source.onopen = () => {
      if (opened) setReloads((n) => n + 1); // catch up on what was missed while away
      opened = true;
    };
    // EventSource reconnects on its own; the status only reflects it.
    source.onerror = () =>
      setStatus((s) => (s === "live" ? "reconnecting" : "offline"));
    source.addEventListener("frame", (e) => {
      const frame = JSON.parse(
        (e as MessageEvent<string>).data,
      ) as TrackingFrame;
      if (clock.current.observe(frame.match_clock_ms)) {
        buffer.current.clear();
        setEvents([]);
        setHistory([]);
        setReloads((n) => n + 1);
      }
      buffer.current.push(frame);
      setStatus("live");
    });
    source.addEventListener("match_event", (e) => {
      const live = JSON.parse((e as MessageEvent<string>).data) as LiveEvent;
      setEvents((known) => mergeEvents([live.event], known));
    });
    source.addEventListener("card", (e) => {
      setCard(JSON.parse((e as MessageEvent<string>).data) as MatchCard);
    });
    source.addEventListener("desk", (e) => {
      setDesk(JSON.parse((e as MessageEvent<string>).data) as Desk);
    });
    return () => source.close();
  }, [matchId, setDesk]);

  // Stable for the life of the page, so the animation loops never restart.
  const frameSource = useMemo<FrameSource>(
    () => ({
      getClockMs: () => clock.current.now() ?? fallbackClock.current,
      frameAt: (clockMs) => buffer.current.at(clockMs),
      ballXAt: (clockMs) => buffer.current.ballXAt(clockMs),
    }),
    [],
  );

  const info = useMemo(() => (detail ? matchInfo(detail) : null), [detail]);
  const baseline = useMemo(
    () =>
      detail
        ? {
            clockMs: detail.card.clock_ms,
            home: detail.card.score_home,
            away: detail.card.score_away,
          }
        : null,
    [detail],
  );

  return {
    status,
    info,
    source: frameSource,
    baseline,
    card,
    events,
    desk,
    history,
    setDesk,
    refreshDesk,
  };
}

function mergeEvents(
  incoming: MatchEvent[],
  known: MatchEvent[],
): MatchEvent[] {
  const byId = new Map(known.map((e) => [e.event_id, e]));
  for (const e of incoming) byId.set(e.event_id, e);
  return [...byId.values()]
    .sort(
      (a, b) =>
        a.match_clock_ms - b.match_clock_ms ||
        a.event_id.localeCompare(b.event_id),
    )
    .slice(-MAX_EVENTS);
}

function mergeAudit(
  incoming: AuditRecord[],
  seen: AuditRecord[],
): AuditRecord[] {
  const known = new Set(seen.map((r) => r.audit_id));
  const fresh = incoming.filter((r) => !known.has(r.audit_id));
  if (!fresh.length) return seen;
  // Newest first, like the desk's own log.
  return [...fresh, ...seen].slice(0, MAX_HISTORY);
}
