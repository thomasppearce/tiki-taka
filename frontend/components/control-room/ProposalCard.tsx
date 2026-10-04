import {
  ChartBar,
  ClockCounterClockwise,
  IdentificationBadge,
  Quotes,
  Receipt,
  Strategy,
  Timer,
} from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";

import { Button } from "@/components/ui/Button";
import type { Proposal } from "@/lib/contracts.generated";
import { formatCountdown } from "@/lib/format";

const TYPE_META: Record<Proposal["type"], { label: string; Icon: Icon }> = {
  stat_graphic: { label: "Stat graphic", Icon: ChartBar },
  narrative_line: { label: "Narrative line", Icon: Quotes },
  tactical_insight: { label: "Tactical insight", Icon: Strategy },
  player_tag: { label: "Player tag", Icon: IdentificationBadge },
  recap_beat: { label: "Recap beat", Icon: ClockCounterClockwise },
};

const URGENT_MS = 20_000;

/** One proposal in the producer's queue. The selected card shows its receipts and actions. */
export function ProposalCard({
  proposal,
  clockMs,
  selected,
}: {
  proposal: Proposal;
  clockMs: number;
  selected: boolean;
}) {
  const { label, Icon } = TYPE_META[proposal.type];
  const remainingMs = proposal.expires_at_clock_ms - clockMs;
  const urgent = remainingMs <= URGENT_MS;

  return (
    <article
      aria-current={selected || undefined}
      className={`rounded-md border p-3 transition-[border-color,background-color] duration-150 ease-out ${
        selected
          ? "border-air bg-raised"
          : "border-line hover:border-line-strong"
      }`}
    >
      <header className="flex items-center justify-between text-xs text-ink-3">
        <span className="flex items-center gap-1.5">
          <Icon size={14} />
          {label}
        </span>
        <span
          className={`flex items-center gap-1 font-mono tabular-nums ${urgent ? "text-warning" : ""}`}
        >
          <Timer size={14} weight={urgent ? "bold" : "regular"} />
          <span className="sr-only">Expires in</span>
          {formatCountdown(remainingMs)}
        </span>
      </header>

      <h3 className="mt-2 text-base leading-snug font-semibold text-ink">
        {proposal.headline}
      </h3>
      <p className="mt-1 text-sm leading-relaxed text-ink-2">
        {proposal.body.analyst.en}
      </p>

      {selected && (
        <ul className="mt-3 space-y-2 border-t border-line pt-3">
          {proposal.claims.map((claim) => (
            <li
              key={claim.text}
              className="flex items-start gap-2 text-label text-ink-2"
            >
              <Receipt size={14} className="mt-0.5 shrink-0 text-ink-3" />
              <span className="flex-1">{claim.text}</span>
              <span className="shrink-0 rounded-md border border-air/60 px-1.5 text-xs text-ink-2 tabular-nums">
                {claim.evidence_event_ids.length}{" "}
                {claim.evidence_event_ids.length === 1 ? "event" : "events"}
              </span>
            </li>
          ))}
        </ul>
      )}

      <footer className="mt-3 flex items-center justify-between gap-3">
        <span className="text-xs text-ink-3">
          <span className="font-mono text-ink-2 tabular-nums">
            {Math.round(proposal.confidence * 100)}%
          </span>{" "}
          confidence
        </span>
        {selected ? (
          <div className="flex gap-1.5">
            <Button shortcut="R">Reject</Button>
            <Button shortcut="E">Edit</Button>
            <Button variant="primary" shortcut="A">
              Approve
            </Button>
          </div>
        ) : (
          <span className="text-xs text-ink-3">
            {proposal.claims.length}{" "}
            {proposal.claims.length === 1 ? "claim" : "claims"}
          </span>
        )}
      </footer>
    </article>
  );
}
