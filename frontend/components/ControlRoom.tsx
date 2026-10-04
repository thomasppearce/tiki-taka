"use client";

import { MotionConfig } from "motion/react";
import {
  type Dispatch,
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
} from "react";

import { AgentActivity } from "@/components/control-room/AgentActivity";
import { MomentumTimeline } from "@/components/control-room/MomentumTimeline";
import { ProgramMonitor } from "@/components/control-room/ProgramMonitor";
import type { CardActions } from "@/components/control-room/ProposalCard";
import { ProposalQueue } from "@/components/control-room/ProposalQueue";
import { TacticalPitch } from "@/components/control-room/TacticalPitch";
import { TopBar } from "@/components/control-room/TopBar";
import {
  type Action,
  type State,
  agentStates,
  createInitialState,
  pendingSorted,
  reducer,
} from "@/lib/controlRoom";
import { formatClock } from "@/lib/format";
import { eventsUntil } from "@/lib/matchSim";
import { MATCH, momentumAt } from "@/lib/mock";

const TICK_MS = 250;

/*
 * The control room. Three layouts, one tree:
 * - xl (>= 1280px): fixed single-screen control room; the left column fills the viewport height.
 * - lg (1024-1279px): page scrolls; panels stack on the left, the proposal queue stays pinned right.
 * - below lg: one column. The column wrappers become `display: contents` so their panels join the
 *   page grid directly and can be ordered: program, proposals, pitch, momentum, agents.
 */
export function ControlRoom() {
  const [state, dispatch] = useReducer(reducer, undefined, createInitialState);
  const getClockMs = useMatchClock(dispatch);
  useShortcuts(state, dispatch);

  const queue = pendingSorted(state);
  const selected =
    queue.find((p) => p.proposal_id === state.selectedId) ?? null;
  const citedEventIds = useMemo(
    () => new Set(selected?.claims.flatMap((c) => c.evidence_event_ids) ?? []),
    [selected],
  );
  const minute = Math.floor(state.clockMs / 60_000);
  const momentum = useMemo(
    () => Array.from({ length: minute + 1 }, (_, m) => momentumAt(m)),
    [minute],
  );
  const clock = formatClock(state.clockMs);
  const events = useMemo(() => eventsUntil(state.clockMs), [state.clockMs]);
  const actions = useMemo<CardActions>(
    () => ({
      onSelect: (id) => dispatch({ type: "select", id }),
      onApprove: (id) => dispatch({ type: "approve", id }),
      onReject: (id) => dispatch({ type: "reject", id }),
      onEdit: (id) => dispatch({ type: "startEdit", id }),
      onCancelEdit: () => dispatch({ type: "cancelEdit" }),
      onSaveEdit: (id, headline, body) =>
        dispatch({ type: "saveEdit", id, headline, body }),
    }),
    [],
  );

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-dvh flex-col bg-page xl:h-dvh xl:min-h-[760px]">
        <TopBar
          clock={clock}
          feed={state.feed}
          onFeedChange={(feed) => dispatch({ type: "setFeed", feed })}
        />
        <main className="grid flex-1 grid-cols-1 gap-3 p-3 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start xl:min-h-0 xl:grid-cols-[minmax(0,1fr)_360px] xl:items-stretch 2xl:grid-cols-[minmax(0,1fr)_400px]">
          <div className="contents lg:grid lg:min-w-0 lg:gap-3 xl:min-h-0 xl:grid-rows-[auto_auto_minmax(0,1fr)]">
            <div className="contents xl:grid xl:min-w-0 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)] xl:gap-3">
              <ProgramMonitor
                clock={clock}
                getClockMs={getClockMs}
                feed={state.feed}
                onAir={state.onAir}
                className="order-1 lg:order-none"
              />
              <TacticalPitch
                events={events}
                getClockMs={getClockMs}
                citedEventIds={citedEventIds}
                className="order-3 lg:order-none"
              />
            </div>
            <MomentumTimeline
              momentum={momentum}
              markers={state.markers}
              nowMinute={minute}
              className="order-4 lg:order-none"
            />
            <AgentActivity
              agents={agentStates(state)}
              log={state.log}
              className="order-5 lg:order-none"
            />
          </div>
          <ProposalQueue
            proposals={queue}
            selectedId={state.selectedId}
            editingId={state.editingId}
            clockMs={state.clockMs}
            feed={state.feed}
            decisions={state.decisions}
            counts={state.counts}
            actions={actions}
            className="order-2 lg:sticky lg:top-3 lg:order-none lg:max-h-[calc(100dvh-1.5rem)] xl:static xl:max-h-none"
          />
        </main>
      </div>
    </MotionConfig>
  );
}

/**
 * The match clock, advancing in real time (1x) from the session start. Returns a stable reader:
 * the reducer ticks from it at 4 Hz for the UI, and the animated views read it every frame, so
 * the camera, the formation board, and the queue all agree on the time.
 */
function useMatchClock(dispatch: Dispatch<Action>): () => number {
  const startedAt = useRef<number | null>(null);
  const getClockMs = useCallback(
    () =>
      MATCH.clockMs +
      (startedAt.current === null ? 0 : performance.now() - startedAt.current),
    [],
  );
  useEffect(() => {
    startedAt.current = performance.now();
    const timer = setInterval(
      () => dispatch({ type: "tick", clockMs: getClockMs() }),
      TICK_MS,
    );
    return () => clearInterval(timer);
  }, [dispatch, getClockMs]);
  return getClockMs;
}

/** J/K or arrows to move, A approve, E edit, R reject. Ignored while typing or with modifiers. */
function useShortcuts(state: State, dispatch: Dispatch<Action>) {
  const latest = useRef(state);
  useEffect(() => {
    latest.current = state;
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable='true']"))
        return;
      const id = latest.current.selectedId;
      const key = e.key.toLowerCase();

      if (key === "j" || key === "arrowdown")
        dispatch({ type: "move", delta: 1 });
      else if (key === "k" || key === "arrowup")
        dispatch({ type: "move", delta: -1 });
      else if (key === "a" && id) dispatch({ type: "approve", id });
      else if (key === "r" && id) dispatch({ type: "reject", id });
      else if (key === "e" && id) dispatch({ type: "startEdit", id });
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dispatch]);
}
