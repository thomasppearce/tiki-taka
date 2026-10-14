"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import type { DrillState } from "@/lib/contracts.generated";
import { useDrill } from "@/lib/live/useDrill";

type DrillAgent = NonNullable<DrillState["agent"]>;

export type DrillTarget = {
  agent: DrillAgent;
  label: string;
  /** What the system does instead when this agent is down. */
  fallback: string;
};

const NAMES: Record<DrillAgent, string> = {
  interpreter: "Interpreter",
  explainer: "Explainer",
  fact_checker: "Fact-checker",
  producer: "Producer",
  localizer: "Localizer",
  watcher: "Watchers",
  director: "Director",
};

/**
 * The failure drill, a demo control: make one agent drop a model call (the orchestrator's retry
 * recovers it) or go down for three minutes (the system falls back), then watch the agents and
 * the log. The backend runs drilled moments live, so the failure and the recovery are real.
 */
export function FailureDrill({ targets }: { targets: DrillTarget[] }) {
  const { drill, busy, start, end } = useDrill();
  const [agent, setAgent] = useState<DrillAgent>(targets[0].agent);

  if (drill?.agent) {
    const target = targets.find((t) => t.agent === drill.agent);
    const name = NAMES[drill.agent];
    const down = drill.mode === "down";
    return (
      <div
        role="status"
        className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-line px-3 py-2"
      >
        <span
          aria-hidden
          className={`size-2 shrink-0 rounded-full ${down ? "bg-critical" : "bg-serious"}`}
        />
        <p className="min-w-0 flex-1 text-xs text-ink-2">
          <span className="font-medium text-ink">
            {down
              ? `${name} down, ${clock(drill.seconds_left)} left.`
              : `${name} will drop its next call.`}
          </span>{" "}
          {down
            ? `Its next run falls back: ${target?.fallback ?? "the code's version airs"}.`
            : "The retry should recover it."}
        </p>
        <Button onClick={() => void end()} disabled={busy}>
          End drill
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2">
      <span className="mr-auto text-xs text-ink-3">
        Failure drill <span className="text-ink-3/70">(demo)</span>
      </span>
      <label className="sr-only" htmlFor="drill-agent">
        Agent to fail
      </label>
      <select
        id="drill-agent"
        value={agent}
        onChange={(e) => setAgent(e.target.value as DrillAgent)}
        className="h-7 rounded-md border border-line bg-page px-1.5 text-label text-ink-2 transition-[border-color] duration-150 ease-out hover:border-line-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-air"
      >
        {targets.map((t) => (
          <option key={t.agent} value={t.agent}>
            {t.label}
          </option>
        ))}
      </select>
      <Button
        onClick={() => void start({ agent, mode: "blip" })}
        disabled={busy}
      >
        Drop one call
      </Button>
      <Button
        onClick={() => void start({ agent, mode: "down" })}
        disabled={busy}
      >
        Take it down
      </Button>
    </div>
  );
}

function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}
