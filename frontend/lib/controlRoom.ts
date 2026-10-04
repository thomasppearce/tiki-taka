/**
 * Control-room state: the clock, the proposal queue, what is on air, and the decision log.
 *
 * Until the real agents stream proposals over SSE, a simulated orchestrator produces them on a
 * schedule (`IncomingJob`), stepping each one through the agent pipeline so the activity panel
 * has real state to show. Every state change is a reducer action, so the backend can later drive
 * the same transitions.
 */

import type { AudienceBody, Proposal } from "@/lib/contracts.generated";
import { formatClock } from "@/lib/format";
import {
  type Audience,
  type Lang,
  ON_AIR_TYPE_LABEL,
  forFeed,
} from "@/lib/i18n";
import {
  INCOMING_TEMPLATES,
  INITIAL_AGENT_STATES,
  INITIAL_AUDIT_LOG,
  INITIAL_ON_AIR,
  MATCH,
  PROPOSALS,
  TIMELINE_MARKERS,
  type TeamId,
} from "@/lib/mock";

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
  status: "done" | "working" | "retrying" | "idle";
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
  team?: TeamId;
  label: string;
};

export type OnAirGraphic = {
  id: string;
  template: "lower_third" | "player_tag";
  label: Record<Lang, string>;
  headline: AudienceBody;
  split?: Record<TeamId, number>;
  splitLabel?: Record<Lang, string>;
  playerId?: string | null;
  startedAtMs: number;
  durationMs: number;
};

export type IncomingTemplate = {
  proposal: Omit<Proposal, "proposal_id" | "moment_id" | "expires_at_clock_ms">;
  ttlMs: number;
  localizerFails: boolean;
};

type Decision = "approved" | "rejected" | "expired";

export type State = {
  clockMs: number;
  /** Pending proposals only; decided ones leave the queue. */
  proposals: Proposal[];
  selectedId: string | null;
  editingId: string | null;
  feed: FeedId;
  onAir: OnAirGraphic | null;
  log: AuditLine[];
  markers: TimelineMarker[];
  counts: { aired: number; rejected: number; expired: number };
  /** Why each proposal left the queue, so its exit animation can match. */
  decisions: Record<string, Decision>;
  /** Index of the next simulated proposal the orchestrator will produce. */
  nextJob: number;
};

export type Action =
  | { type: "tick"; clockMs: number }
  | { type: "select"; id: string }
  | { type: "move"; delta: 1 | -1 }
  | { type: "approve"; id: string }
  | { type: "reject"; id: string }
  | { type: "startEdit"; id: string }
  | { type: "cancelEdit" }
  | { type: "saveEdit"; id: string; headline: string; body: string }
  | { type: "setFeed"; feed: FeedId };

const ON_AIR_MS = 7_000;
const FIRST_ARRIVAL_MS = 12_000;
const ARRIVAL_EVERY_MS = 30_000;
const STAGE_MS = {
  interpreter: 1_200,
  explainer: 1_800,
  producer: 800,
  localizer: 1_600,
};
const PIPELINE: (keyof typeof STAGE_MS)[] = [
  "interpreter",
  "explainer",
  "producer",
  "localizer",
];
const MAX_LOG = 40;

export function createInitialState(): State {
  return {
    clockMs: MATCH.clockMs,
    proposals: PROPOSALS,
    selectedId: PROPOSALS[0].proposal_id,
    editingId: null,
    feed: "feed_analyst_en",
    onAir: INITIAL_ON_AIR,
    log: INITIAL_AUDIT_LOG,
    markers: TIMELINE_MARKERS,
    counts: { aired: 11, rejected: 4, expired: 2 },
    decisions: {},
    nextJob: 0,
  };
}

// --- Simulated orchestrator ------------------------------------------------------------------

type Job = {
  index: number;
  arriveAtMs: number;
  startAtMs: number;
  template: IncomingTemplate;
};

function job(index: number): Job {
  const template = INCOMING_TEMPLATES[index % INCOMING_TEMPLATES.length];
  const arriveAtMs =
    MATCH.clockMs + FIRST_ARRIVAL_MS + index * ARRIVAL_EVERY_MS;
  return {
    index,
    arriveAtMs,
    startAtMs: arriveAtMs - pipelineMs(template),
    template,
  };
}

function pipelineMs(template: IncomingTemplate): number {
  const total = PIPELINE.reduce((sum, stage) => sum + STAGE_MS[stage], 0);
  return total + (template.localizerFails ? STAGE_MS.localizer : 0);
}

function proposalFromJob(j: Job): Proposal {
  const n = 144 + j.index;
  return {
    ...j.template.proposal,
    proposal_id: `prop_${String(n).padStart(4, "0")}`,
    moment_id: `mom_${String(n - 54).padStart(4, "0")}`,
    expires_at_clock_ms: j.arriveAtMs + j.template.ttlMs,
  };
}

const STAGE_COPY: Record<
  keyof typeof STAGE_MS,
  { working: string; done: string }
> = {
  interpreter: {
    working: "Scanning aggregated match state",
    done: "Moment detected",
  },
  explainer: {
    working: "Grounding claims in events and knowledge",
    done: "Claims grounded in cited events",
  },
  producer: {
    working: "Ranking against the queue",
    done: "Ranked and given an expiry",
  },
  localizer: {
    working: "Writing audience and language variants",
    done: "4 variants written",
  },
};

/** What each agent is doing right now, derived from the clock and the orchestrator schedule. */
export function agentStates(state: State): AgentState[] {
  const active = job(state.nextJob);
  const renderer: AgentState = state.onAir
    ? {
        agent: "renderer",
        status: "working",
        detail: `On air for ${FEEDS[state.feed].label}`,
      }
    : {
        agent: "renderer",
        status: "idle",
        detail: state.proposals.length
          ? "Waiting for approval"
          : "Nothing to render",
      };

  if (state.clockMs < active.startAtMs) {
    if (state.nextJob === 0)
      return [...INITIAL_AGENT_STATES.slice(0, 4), renderer];
    return PIPELINE.map(
      (agent) =>
        ({
          agent,
          status: "done",
          detail: STAGE_COPY[agent].done,
        }) as AgentState,
    ).concat(renderer);
  }

  let t = state.clockMs - active.startAtMs;
  const states = PIPELINE.map((agent): AgentState => {
    const stageMs = STAGE_MS[agent];
    if (agent === "localizer" && active.template.localizerFails) {
      if (t < 0) return { agent, status: "idle", detail: "Waiting" };
      if (t < stageMs)
        return {
          agent,
          status: "working",
          detail: STAGE_COPY.localizer.working,
        };
      if (t < stageMs * 2) {
        return {
          agent,
          status: "retrying",
          detail: "Spanish variant failed schema, retry 1 of 3",
        };
      }
      return {
        agent,
        status: "done",
        detail: "4 variants written after 1 retry",
      };
    }
    const result: AgentState =
      t < 0
        ? { agent, status: "idle", detail: "Waiting" }
        : t < stageMs
          ? { agent, status: "working", detail: STAGE_COPY[agent].working }
          : { agent, status: "done", detail: STAGE_COPY[agent].done };
    t -= stageMs;
    return result;
  });
  return [...states, renderer];
}

// --- Reducer ---------------------------------------------------------------------------------

export function pendingSorted(state: State): Proposal[] {
  return [...state.proposals].sort((a, b) => b.priority - a.priority);
}

export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "tick":
      return tick(state, action.clockMs);
    case "select":
      return state.proposals.some((p) => p.proposal_id === action.id)
        ? { ...state, selectedId: action.id, editingId: null }
        : state;
    case "move": {
      const ordered = pendingSorted(state);
      if (!ordered.length) return state;
      const at = ordered.findIndex((p) => p.proposal_id === state.selectedId);
      const next = Math.min(ordered.length - 1, Math.max(0, at + action.delta));
      return {
        ...state,
        selectedId: ordered[next].proposal_id,
        editingId: null,
      };
    }
    case "approve":
      return decide(state, action.id, "approved");
    case "reject":
      return decide(state, action.id, "rejected");
    case "startEdit":
      return { ...state, selectedId: action.id, editingId: action.id };
    case "cancelEdit":
      return { ...state, editingId: null };
    case "saveEdit": {
      const { audience, lang } = FEEDS[state.feed];
      const edited = state.proposals.map((p) =>
        p.proposal_id === action.id
          ? {
              ...p,
              status: "edited" as const,
              headline: withCopy(p.headline, audience, lang, action.headline),
              body: withCopy(p.body, audience, lang, action.body),
            }
          : p,
      );
      return decide(
        { ...state, proposals: edited },
        action.id,
        "approved",
        true,
      );
    }
    case "setFeed":
      return { ...state, feed: action.feed };
  }
}

function withCopy(
  copy: AudienceBody,
  audience: Audience,
  lang: Lang,
  text: string,
): AudienceBody {
  return { ...copy, [audience]: { ...copy[audience], [lang]: text } };
}

function decide(
  state: State,
  id: string,
  decision: Decision,
  edited = false,
): State {
  const proposal = state.proposals.find((p) => p.proposal_id === id);
  if (!proposal) return state;
  const { audience, lang, label } = FEEDS[state.feed];
  const remaining = state.proposals.filter((p) => p.proposal_id !== id);
  const headline = forFeed(proposal.headline, audience, lang);

  let next: State = {
    ...state,
    proposals: remaining,
    editingId: null,
    decisions: { ...state.decisions, [id]: decision },
    selectedId:
      state.selectedId === id ? nextSelection(state, id) : state.selectedId,
  };

  if (decision === "approved") {
    next = {
      ...next,
      onAir: {
        id: `ovl_${id.slice(5)}`,
        template:
          proposal.type === "player_tag" && proposal.player_id
            ? "player_tag"
            : "lower_third",
        label: ON_AIR_TYPE_LABEL[proposal.type],
        headline: proposal.headline,
        playerId: proposal.player_id,
        startedAtMs: state.clockMs,
        durationMs: ON_AIR_MS,
      },
      counts: { ...next.counts, aired: next.counts.aired + 1 },
      markers: [
        ...next.markers,
        {
          minute: Math.floor(state.clockMs / 60_000),
          kind: "aired",
          label: `Aired: ${headline}`,
        },
      ],
    };
    next = log(
      next,
      "you",
      `${edited ? "Edited and approved" : "Approved"} ${id} for ${label}`,
    );
  } else if (decision === "rejected") {
    next = {
      ...next,
      counts: { ...next.counts, rejected: next.counts.rejected + 1 },
    };
    next = log(next, "you", `Rejected ${id}`);
  } else {
    next = {
      ...next,
      counts: { ...next.counts, expired: next.counts.expired + 1 },
    };
    next = log(next, "producer", `Expired ${id} without a decision`);
  }
  return next;
}

function nextSelection(state: State, leavingId: string): string | null {
  const ordered = pendingSorted(state);
  const at = ordered.findIndex((p) => p.proposal_id === leavingId);
  const rest = ordered.filter((p) => p.proposal_id !== leavingId);
  return rest[Math.min(at, rest.length - 1)]?.proposal_id ?? null;
}

function log(state: State, actor: string, text: string): State {
  const line: AuditLine = {
    id: `${state.clockMs}-${state.log.length}-${actor}`,
    clock: formatClock(state.clockMs),
    actor,
    text,
  };
  return { ...state, log: [line, ...state.log].slice(0, MAX_LOG) };
}

function tick(state: State, clockMs: number): State {
  const before = state.clockMs;
  if (clockMs <= before) return state;
  let next: State = { ...state, clockMs };
  const now = next.clockMs;

  // The orchestrator: log the localizer failure as it happens, then deliver the proposal.
  const active = job(next.nextJob);
  const failAt =
    active.startAtMs + pipelineMs(active.template) - STAGE_MS.localizer;
  if (active.template.localizerFails && before < failAt && now >= failAt) {
    next = log(
      next,
      "localizer",
      "es variant failed schema validation, retrying (1 of 3)",
    );
  }
  if (now >= active.arriveAtMs) {
    const proposal = proposalFromJob(active);
    next = {
      ...next,
      proposals: [...next.proposals, proposal],
      nextJob: next.nextJob + 1,
      selectedId: next.selectedId ?? proposal.proposal_id,
      markers: [
        ...next.markers,
        {
          minute: Math.floor(now / 60_000),
          kind: "moment",
          label: forFeed(proposal.headline, "analyst", "en"),
        },
      ],
    };
    next = log(
      next,
      "producer",
      `Queued ${proposal.proposal_id} at priority ${proposal.priority.toFixed(2)}`,
    );
  }

  for (const p of next.proposals) {
    if (p.expires_at_clock_ms <= now)
      next = decide(next, p.proposal_id, "expired");
  }

  if (next.onAir && now >= next.onAir.startedAtMs + next.onAir.durationMs) {
    next = { ...next, onAir: null };
  }
  return next;
}
