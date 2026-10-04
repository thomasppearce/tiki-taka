"use client";

import { MotionConfig } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AgentActivity } from "@/components/control-room/AgentActivity";
import { MomentumTimeline } from "@/components/control-room/MomentumTimeline";
import { ProgramMonitor } from "@/components/control-room/ProgramMonitor";
import type { CardActions } from "@/components/control-room/ProposalCard";
import { ProposalQueue } from "@/components/control-room/ProposalQueue";
import { TacticalPitch } from "@/components/control-room/TacticalPitch";
import { TopBar } from "@/components/control-room/TopBar";
import { FeedState } from "@/components/match/FeedState";
import { postJson } from "@/lib/api";
import type { Desk, Proposal } from "@/lib/contracts.generated";
import {
  type Decisions,
  FEEDS,
  type FeedId,
  agentStates,
  auditLines,
  countsFrom,
  decisionsFrom,
  onAirGraphic,
  pendingQueue,
  scoreAt,
  timelineMarkers,
} from "@/lib/controlRoom";
import { formatClock } from "@/lib/format";
import { useEvidence } from "@/lib/live/useEvidence";
import { usePlaybackClock } from "@/lib/live/usePlaybackClock";
import { type LiveMatch, useLiveMatch } from "@/lib/live/useLiveMatch";
import { MatchContext, type MatchInfo } from "@/lib/match";

const HALF_MS = 45 * 60_000;

type Baseline = NonNullable<LiveMatch["baseline"]>;

/**
 * The producer's control room for one match, live from the backend: the match plays from the
 * tracking stream, and the queue, the on-air graphic, the agents, and the decision log come from
 * the proposal desk. Approving, editing, and rejecting go to the desk's API.
 */
export function ControlRoom({ matchId }: { matchId: string }) {
  const live = useLiveMatch(matchId);
  if (!live.info || !live.baseline)
    return (
      <div className="flex min-h-dvh flex-col bg-page">
        <FeedState status={live.status} />
      </div>
    );
  return (
    <MatchContext value={live.info}>
      <Room live={live} info={live.info} baseline={live.baseline} />
    </MatchContext>
  );
}

/*
 * Three layouts, one tree:
 * - xl (>= 1280px): fixed single-screen control room; the left column fills the viewport height.
 * - lg (1024-1279px): page scrolls; panels stack on the left, the proposal queue stays pinned right.
 * - below lg: one column. The column wrappers become `display: contents` so their panels join the
 *   page grid directly and can be ordered: program, proposals, pitch, momentum, agents.
 */
function Room({
  live,
  info,
  baseline,
}: {
  live: LiveMatch;
  info: MatchInfo;
  baseline: Baseline;
}) {
  const [feed, setFeed] = useState<FeedId>("feed_analyst_en");
  const [chosenId, setChosenId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [inFlight, setInFlight] = useState<Decisions>({});
  const clockMs = usePlaybackClock(live.source.getClockMs);
  const { desk, setDesk, refreshDesk } = live;

  const queue = useMemo(() => pendingQueue(desk, inFlight), [desk, inFlight]);
  // The producer's pick, or the top of the queue once that one has gone.
  const selected =
    queue.find((p) => p.proposal_id === chosenId) ?? queue[0] ?? null;
  const selectedId = selected?.proposal_id ?? null;
  const citedIds = useMemo(
    () => selected?.claims.flatMap((c) => c.evidence_event_ids) ?? [],
    [selected],
  );
  const citedEventIds = useMemo(() => new Set(citedIds), [citedIds]);

  const events = useMemo(
    () => live.events.filter((e) => e.match_clock_ms <= clockMs),
    [live.events, clockMs],
  );
  const older = useEvidence(info.matchId, citedIds, events);
  const pitchEvents = useMemo(() => [...older, ...events], [older, events]);
  const score = scoreAt(info, baseline, live.events, clockMs);
  const minute = Math.floor(clockMs / 60_000);
  const momentum = useMemo(
    () => (live.card?.momentum ?? []).slice(0, minute + 1),
    [live.card, minute],
  );
  const markers = useMemo(
    () => timelineMarkers(info, events, live.history),
    [info, events, live.history],
  );
  const decisions = useMemo(
    () => decisionsFrom(live.history, inFlight),
    [live.history, inFlight],
  );
  const clock = formatClock(clockMs);
  const period =
    live.card?.status === "full_time"
      ? "Full time"
      : clockMs < HALF_MS
        ? "1st half"
        : "2nd half";

  const decide = useCallback(
    async (
      id: string,
      decision: "approved" | "rejected",
      edit?: { headline: string; body: string },
    ) => {
      // The card leaves at once; the desk's answer confirms it, or the card comes back.
      setInFlight((d) => ({ ...d, [id]: decision }));
      setEditingId(null);
      try {
        const action = decision === "approved" ? "approve" : "reject";
        const body =
          decision === "approved" ? { profile_id: feed, ...edit } : {};
        setDesk(
          await postJson<Desk>(
            `/api/matches/${info.matchId}/proposals/${id}/${action}`,
            body,
          ),
        );
      } catch {
        // Expired or already decided on the server: show the desk as it now is.
        await refreshDesk();
      } finally {
        setInFlight((d) => {
          const rest = { ...d };
          delete rest[id];
          return rest;
        });
      }
    },
    [feed, info.matchId, setDesk, refreshDesk],
  );

  const actions = useMemo<CardActions>(
    () => ({
      onSelect: (id) => {
        setChosenId(id);
        setEditingId(null);
      },
      onApprove: (id) => void decide(id, "approved"),
      onReject: (id) => void decide(id, "rejected"),
      onEdit: (id) => {
        setChosenId(id);
        setEditingId(id);
      },
      onCancelEdit: () => setEditingId(null),
      onSaveEdit: (id, headline, body) =>
        void decide(id, "approved", { headline, body }),
    }),
    [decide],
  );
  useShortcuts(queue, selectedId, actions);

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-dvh flex-col bg-page xl:h-dvh xl:min-h-[760px]">
        <TopBar
          clock={clock}
          period={period}
          score={score}
          status={live.status}
          feed={feed}
          onFeedChange={setFeed}
        />
        <main className="grid flex-1 grid-cols-1 gap-3 p-3 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start xl:min-h-0 xl:grid-cols-[minmax(0,1fr)_360px] xl:items-stretch 2xl:grid-cols-[minmax(0,1fr)_400px]">
          <div className="contents lg:grid lg:min-w-0 lg:gap-3 xl:min-h-0 xl:grid-rows-[auto_auto_minmax(0,1fr)]">
            <div className="contents xl:grid xl:min-w-0 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)] xl:gap-3">
              <ProgramMonitor
                clock={clock}
                source={live.source}
                score={score}
                view={FEEDS[feed]}
                onAir={onAirGraphic(desk)}
                className="order-1 lg:order-none"
              />
              <TacticalPitch
                events={pitchEvents}
                source={live.source}
                citedEventIds={citedEventIds}
                className="order-3 lg:order-none"
              />
            </div>
            <MomentumTimeline
              momentum={momentum}
              markers={markers}
              nowMinute={minute}
              className="order-4 lg:order-none"
            />
            <AgentActivity
              agents={agentStates(desk, FEEDS[feed].label)}
              log={auditLines(desk)}
              className="order-5 lg:order-none"
            />
          </div>
          <ProposalQueue
            proposals={queue}
            selectedId={selectedId}
            editingId={editingId}
            clockMs={clockMs}
            feed={feed}
            decisions={decisions}
            counts={countsFrom(desk)}
            actions={actions}
            className="order-2 lg:sticky lg:top-3 lg:order-none lg:max-h-[calc(100dvh-1.5rem)] xl:static xl:max-h-none"
          />
        </main>
      </div>
    </MotionConfig>
  );
}

/** J/K or arrows to move, A approve, E edit, R reject. Ignored while typing or with modifiers. */
function useShortcuts(
  queue: Proposal[],
  selectedId: string | null,
  actions: CardActions,
) {
  const latest = useRef({ queue, selectedId, actions });
  useEffect(() => {
    latest.current = { queue, selectedId, actions };
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable='true']"))
        return;
      const { queue, selectedId: id, actions } = latest.current;
      const key = e.key.toLowerCase();
      const move = (delta: 1 | -1) => {
        if (!queue.length) return;
        const at = queue.findIndex((p) => p.proposal_id === id);
        const next = Math.min(queue.length - 1, Math.max(0, at + delta));
        actions.onSelect(queue[next].proposal_id);
      };

      if (key === "j" || key === "arrowdown") move(1);
      else if (key === "k" || key === "arrowup") move(-1);
      else if (key === "a" && id) actions.onApprove(id);
      else if (key === "r" && id) actions.onReject(id);
      else if (key === "e" && id) actions.onEdit(id);
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
