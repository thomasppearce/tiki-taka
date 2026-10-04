import {
  ArrowsClockwise,
  BookOpenText,
  CaretRight,
  CheckCircle,
  Circle,
  CircleNotch,
  Funnel,
  MagnifyingGlass,
  MonitorPlay,
  Translate,
} from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";
import { Fragment } from "react";

import { Panel } from "@/components/ui/Panel";
import type { AgentName, AgentState, AuditLine } from "@/lib/mock";

const AGENT_META: Partial<Record<AgentName, { label: string; Icon: Icon }>> = {
  interpreter: { label: "Interpreter", Icon: MagnifyingGlass },
  explainer: { label: "Explainer", Icon: BookOpenText },
  producer: { label: "Producer", Icon: Funnel },
  localizer: { label: "Localizer", Icon: Translate },
  renderer: { label: "Renderer", Icon: MonitorPlay },
};

const STATUS_META: Record<
  AgentState["status"],
  { label: string; Icon: Icon; tone: string }
> = {
  done: { label: "Done", Icon: CheckCircle, tone: "text-good" },
  working: { label: "Working", Icon: CircleNotch, tone: "text-ink-2" },
  retrying: { label: "Retrying", Icon: ArrowsClockwise, tone: "text-serious" },
  idle: { label: "Idle", Icon: Circle, tone: "text-ink-3" },
};

/** The agent pipeline for the selected proposal, then the decision log (audit trail). */
export function AgentActivity({
  agents,
  log,
}: {
  agents: AgentState[];
  log: AuditLine[];
}) {
  const retrying = agents.filter((a) => a.status === "retrying").length;

  return (
    <Panel
      title="Agents"
      aside={<Health retrying={retrying} />}
      className="min-h-0"
    >
      <ol className="flex items-stretch gap-1 border-b border-line p-2.5">
        {agents.map((state, i) => (
          <Fragment key={state.agent}>
            {i > 0 && (
              <li aria-hidden className="flex items-center text-line-strong">
                <CaretRight size={14} />
              </li>
            )}
            <AgentStep state={state} />
          </Fragment>
        ))}
      </ol>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2.5">
        <h3 className="sr-only">Decision log</h3>
        <ol className="grid grid-cols-[auto_6rem_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-xs">
          {log.map((line) => (
            <li key={`${line.clock}-${line.text}`} className="contents">
              <span className="font-mono text-ink-3 tabular-nums">
                {line.clock}
              </span>
              <span className="text-ink-2">{line.actor}</span>
              <span className="truncate text-ink-3">{line.text}</span>
            </li>
          ))}
        </ol>
      </div>
    </Panel>
  );
}

function Health({ retrying }: { retrying: number }) {
  return retrying > 0 ? (
    <span className="flex items-center gap-1.5 text-xs text-serious">
      <ArrowsClockwise size={14} />
      {retrying} retrying
    </span>
  ) : (
    <span className="flex items-center gap-1.5 text-xs text-good">
      <CheckCircle size={14} />
      All healthy
    </span>
  );
}

function AgentStep({ state }: { state: AgentState }) {
  const meta = AGENT_META[state.agent];
  if (!meta) return null;
  const status = STATUS_META[state.status];
  return (
    <li
      className={`flex min-w-0 flex-1 flex-col gap-1 rounded-md border px-2.5 py-2 ${
        state.status === "retrying" ? "border-serious/50" : "border-line"
      }`}
    >
      <span className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-label font-medium text-ink">
          <meta.Icon size={14} className="text-ink-3" />
          {meta.label}
        </span>
        <span className={`flex items-center gap-1 text-xs ${status.tone}`}>
          <status.Icon size={12} weight="bold" />
          {status.label}
        </span>
      </span>
      <span className="text-xs text-ink-3">{state.detail}</span>
    </li>
  );
}
