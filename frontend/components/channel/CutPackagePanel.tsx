"use client";

import { Receipt } from "@phosphor-icons/react/dist/ssr";

import { Panel } from "@/components/ui/Panel";
import type { Channel, Cut, TableSwing } from "@/lib/contracts.generated";

const DECIDED_BY: Record<Cut["decided_by"], string> = {
  code: "Director",
  director: "Director agent",
  producer: "Producer",
};

const REASON: Record<Cut["reason"], string> = {
  goal: "Goal",
  pressure: "Pressure",
  check_in: "Check-in",
  manual: "Producer's call",
  kickoff: "Start",
};

/**
 * Why the feed is where it is: the package for the cut on air (why we're here, what's at stake,
 * the story so far, and how many events back it up), then the cuts before it.
 */
export function CutPackagePanel({
  channel,
  fixtureOf,
}: {
  channel: Channel;
  fixtureOf: (matchId: string) => string;
}) {
  const cut = channel.on_air;
  const { why, at_stake: atStake, story, claims } = cut.package;
  const receipts = new Set(claims.flatMap((c) => c.evidence_event_ids)).size;
  return (
    <Panel
      title="Why we're here"
      aside={
        <span className="text-xs text-ink-3">
          {REASON[cut.reason]} · {DECIDED_BY[cut.decided_by]} ·{" "}
          {minute(cut.clock_ms)}
        </span>
      }
    >
      <div className="grid gap-3 p-3">
        <div>
          <p className="text-xs text-ink-3">{fixtureOf(cut.match_id)}</p>
          <p className="mt-1 text-base leading-snug text-ink">{why}</p>
        </div>
        {atStake && <p className="text-sm text-ink-2">{atStake}</p>}
        <div className="border-t border-line pt-3">
          <h3 className="text-xs text-ink-3">Story so far</h3>
          <p className="mt-1 text-sm text-ink-2">{story}</p>
        </div>
        {receipts > 0 && (
          <p className="flex items-center gap-1.5 text-xs text-ink-3">
            <Receipt size={14} />
            Backed by {receipts} match {receipts === 1 ? "event" : "events"}
          </p>
        )}
      </div>
      {channel.history.length > 0 && (
        <div className="border-t border-line">
          <h3 className="px-3 pt-2 text-xs text-ink-3">Earlier cuts</h3>
          <ol className="max-h-48 overflow-y-auto px-3 pt-1 pb-2 text-sm">
            {channel.history.map((c) => (
              <li
                key={c.cut_id}
                className="grid grid-cols-[3rem_minmax(0,1fr)] gap-x-2 py-1"
              >
                <span className="font-mono text-xs text-ink-3 tabular-nums">
                  {minute(c.clock_ms)}
                </span>
                <span className="truncate text-ink-2">
                  <span className="text-ink">{fixtureOf(c.match_id)}</span> ·{" "}
                  {c.package.why}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </Panel>
  );
}

/** The day's story in the table: every goal that moved a club into or out of a zone. */
export function TableMoves({ swings }: { swings: TableSwing[] }) {
  const newest = [...swings].reverse();
  return (
    <Panel title="Table moves today">
      {newest.length ? (
        <ol className="grid gap-2 p-3 text-sm">
          {newest.map((s) => (
            <li
              key={s.event_id}
              className="grid grid-cols-[3rem_minmax(0,1fr)] gap-x-2"
            >
              <span className="font-mono text-xs leading-5 text-ink-3 tabular-nums">
                {minute(s.match_clock_ms)}
              </span>
              <span className="text-ink-2">{s.summary}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="p-3 text-sm text-ink-3">
          Nobody has moved into or out of a zone yet. Every goal that changes
          the title, the top four, or the drop appears here.
        </p>
      )}
    </Panel>
  );
}

function minute(clockMs: number): string {
  return `${Math.floor(clockMs / 60_000) + 1}'`;
}
