/**
 * The control room's reading of the proposal desk. The backend owns the queue, what is on air,
 * and the audit log (GET/POST /api/matches/{id}/desk, and `desk` on the live stream); these
 * helpers turn a Desk snapshot into what each panel draws. The page keeps only the producer's
 * own state: the selection, an edit in progress, the feed, and decisions still in flight.
 */

import type {
  AudienceBody,
  AuditRecord,
  Desk,
  MatchEvent,
  Proposal,
} from "@/lib/contracts.generated";
import { formatClock } from "@/lib/format";
import { type Audience, type Lang, ON_AIR_TYPE_LABEL } from "@/lib/i18n";
import { type MatchInfo, type Side, sideOf, surname } from "@/lib/match";

export type FeedId = "feed_analyst_en" | "feed_casual_es";

export const FEEDS: Record<
  FeedId,
  { audience: Audience; lang: Lang; label: string }
> = {
  feed_analyst_en: { audience: "analyst", lang: "en", label: "Analyst EN" },
  feed_casual_es: { audience: "casual", lang: "es", label: "Casual ES" },
};

export type AgentName = Proposal["produced_by"][number];

export type AgentState = {
  agent: AgentName;
  status: "done" | "working" | "retrying" | "down" | "idle";
  detail: string;
};

export type AuditLine = {
  id: string;
  clock: string;
  actor: string;
  text: string;
};

export type TimelineMarker = {
  minute: number;
  kind: "goal" | "moment" | "aired";
  team?: Side;
  label: string;
};

export type OnAirGraphic = {
  id: string;
  template: "lower_third" | "player_tag";
  label: Record<Lang, string>;
  headline: AudienceBody;
  split?: Record<Side, number>;
  splitLabel?: Record<Lang, string>;
  playerId?: string | null;
  startedAtMs: number;
  durationMs: number;
};

export type Decision = "approved" | "rejected" | "expired";
export type Decisions = Record<string, Decision>;
export type Counts = { aired: number; rejected: number; expired: number };

const PIPELINE: AgentName[] = [
  "interpreter",
  "explainer",
  "checker",
  "fact_checker",
  "producer",
  "localizer",
];

const WORKING: Partial<Record<AgentName, string>> = {
  interpreter: "Scanning the match state",
  explainer: "Grounding claims in events and knowledge",
  checker: "Checking every claim against the events",
  fact_checker: "Reading the graphic against what happened",
  producer: "Ranking against the queue",
  localizer: "Writing audience and language variants",
};

/** Pending proposals, highest priority first, minus any the producer just decided. */
export function pendingQueue(
  desk: Desk | null,
  inFlight: Decisions,
): Proposal[] {
  return (desk?.proposals ?? [])
    .filter((p) => !inFlight[p.proposal_id])
    .sort((a, b) => b.priority - a.priority);
}

/** Why each proposal left the queue, so its exit animation can say so. */
export function decisionsFrom(
  history: AuditRecord[],
  inFlight: Decisions,
): Decisions {
  const decisions: Decisions = {};
  for (const r of history) {
    if (
      r.proposal_id &&
      (r.action === "approved" ||
        r.action === "rejected" ||
        r.action === "expired")
    )
      decisions[r.proposal_id] ??= r.action;
  }
  return { ...decisions, ...inFlight };
}

export function countsFrom(desk: Desk | null): Counts {
  return {
    aired: desk?.aired ?? 0,
    rejected: desk?.rejected ?? 0,
    expired: desk?.expired ?? 0,
  };
}

/** A goal's graphic is labelled as one, whatever kind of graphic it is. */
const GOAL_LABEL: Record<Lang, string> = { en: "Goal", es: "Gol" };

/** The desk's graphic on air. `events` (the match's) tell a goal's graphic apart: its moment
 * is named after the goal (app/state/aggregator.py: km_ + the event's number). */
export function onAirGraphic(
  desk: Desk | null,
  events: readonly MatchEvent[] = [],
): OnAirGraphic | null {
  const air = desk?.on_air;
  if (!air) return null;
  const proposal = air.proposal;
  const goalId = `evt_${proposal.moment_id.slice(3)}`;
  const goal = events.some((e) => e.event_id === goalId && e.type === "goal");
  return {
    id: `ovl_${proposal.proposal_id.slice(5)}`,
    template: air.template === "player_tag" ? "player_tag" : "lower_third",
    label: goal ? GOAL_LABEL : ON_AIR_TYPE_LABEL[proposal.type],
    headline: proposal.headline,
    playerId: proposal.player_id,
    startedAtMs: air.start_clock_ms,
    durationMs: air.duration_ms,
  };
}

/**
 * Where the agent pipeline is for the newest moment: every agent that has reported since the
 * Interpreter last picked something up is done (or retrying, after a failure); the next one is
 * working; the rest are waiting. The Renderer is working while a graphic is on air.
 */
export function agentStates(
  desk: Desk | null,
  feedLabel: string,
): AgentState[] {
  const renderer: AgentState = desk?.on_air
    ? {
        agent: "renderer",
        status: "working",
        detail: `On air for ${feedLabel}`,
      }
    : {
        agent: "renderer",
        status: "idle",
        detail: desk?.proposals.length
          ? "Waiting for approval"
          : "Nothing to render",
      };
  const audit = desk?.audit ?? [];
  const start = audit.findIndex(
    (r) => r.actor === "interpreter" && r.action === "handoff",
  );
  if (start < 0) {
    return [
      ...PIPELINE.map((agent): AgentState => ({
        agent,
        status: "idle",
        detail: "Watching the match",
      })),
      renderer,
    ];
  }
  const run = audit.slice(0, start + 1);
  const finished = run.some(
    (r) =>
      r.action === "created" ||
      (r.actor === "producer" && r.detail?.startsWith("Held back")),
  );
  // The run gave up and the scripted copy went out (an agent was down): whoever never got to
  // report was skipped, not done.
  const fellBack = run.some(
    (r) => r.actor === "orchestrator" && r.action === "agent_failure",
  );
  let next = true;
  const states = PIPELINE.map((agent): AgentState => {
    // The agent's own reports (decisions the producer logs, like expiries, don't count).
    const latest = run.find(
      (r) =>
        r.actor === agent &&
        (r.action === "handoff" ||
          r.action === "agent_failure" ||
          r.action === "retry"),
    );
    if (latest?.action === "agent_failure") {
      // An agent whose last word was a failed model call, on a run that has ended, went down
      // (a failure drill, or an outage). Other failures are a check sending work back.
      const down = finished && (latest.detail ?? "").startsWith("Call failed");
      return {
        agent,
        status: down ? "down" : "retrying",
        detail: latest.detail ?? "Retrying",
      };
    }
    if (!latest && finished && fellBack)
      return {
        agent,
        status: "idle",
        detail: "Skipped: the scripted copy went out",
      };
    if (latest || finished)
      return { agent, status: "done", detail: latest?.detail ?? "Done" };
    if (next) {
      next = false;
      return { agent, status: "working", detail: WORKING[agent] ?? "Working" };
    }
    return { agent, status: "idle", detail: "Waiting" };
  });
  return [...states, renderer];
}

/** The decision log as the panel prints it, newest first. */
export function auditLines(desk: Desk | null): AuditLine[] {
  return (desk?.audit ?? []).map((r) => ({
    id: r.audit_id,
    clock: formatClock(r.match_clock_ms ?? desk?.clock_ms ?? 0),
    actor: r.actor_type === "human" ? "you" : r.actor,
    text: describe(r),
  }));
}

function describe(r: AuditRecord): string {
  const id = r.proposal_id ?? "";
  const detail = r.detail ?? "";
  switch (r.action) {
    case "created":
      return `Queued ${id}: ${detail}`;
    case "approved":
      return `Approved ${id}${r.actor === "autopilot" ? " on autopilot" : ""}: ${detail}`;
    case "edited":
      return `${detail} (${id})`;
    case "rejected":
      return `Rejected ${id}: ${detail}`;
    case "expired":
      return `Expired ${id} without a decision`;
    default:
      return detail;
  }
}

/** Goals so far, plus everything aired this session, for the momentum timeline. */
export function timelineMarkers(
  info: MatchInfo,
  events: MatchEvent[],
  history: AuditRecord[],
): TimelineMarker[] {
  const goals = events
    .filter((e) => e.type === "goal")
    .map((e): TimelineMarker => ({
      minute: e.minute,
      kind: "goal",
      team: sideOf(info, e.team_id),
      label: `Goal: ${surname(info.players.get(e.player_id ?? "")?.name ?? "")}`,
    }));
  const aired = history
    .filter((r) => r.action === "approved" && r.match_clock_ms !== null)
    .map((r): TimelineMarker => ({
      minute: Math.floor((r.match_clock_ms ?? 0) / 60_000),
      kind: "aired",
      label: `Aired: ${r.detail ?? r.proposal_id}`,
    }));
  return [...goals, ...aired];
}

/** The score at `clockMs`: the score when the page loaded, plus goals since. */
export function scoreAt(
  info: MatchInfo,
  baseline: { clockMs: number; home: number; away: number },
  events: MatchEvent[],
  clockMs: number,
): Record<Side, number> {
  const score = { home: baseline.home, away: baseline.away };
  for (const e of events) {
    if (
      e.type === "goal" &&
      e.match_clock_ms > baseline.clockMs &&
      e.match_clock_ms <= clockMs
    )
      score[sideOf(info, e.team_id)] += 1;
  }
  return score;
}
