import { ProposalCard } from "@/components/control-room/ProposalCard";
import { Kbd } from "@/components/ui/Kbd";
import { Panel } from "@/components/ui/Panel";
import type { Proposal } from "@/lib/contracts.generated";

/** The producer's queue: pending proposals, highest priority first. */
export function ProposalQueue({
  proposals,
  selectedId,
  clockMs,
  className,
}: {
  proposals: Proposal[];
  selectedId: string | null;
  clockMs: number;
  className?: string;
}) {
  const pending = [...proposals]
    .filter((p) => p.status === "pending")
    .sort((a, b) => b.priority - a.priority);

  return (
    <Panel
      title="Proposals"
      aside={
        <span className="text-xs text-ink-3 tabular-nums">
          {pending.length} pending
        </span>
      }
      className={className}
    >
      <p className="hidden flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-3 py-2 text-xs text-ink-3 lg:flex">
        <span className="flex items-center gap-1">
          <Kbd>J</Kbd>
          <Kbd>K</Kbd> move
        </span>
        <span className="flex items-center gap-1">
          <Kbd>A</Kbd> approve
        </span>
        <span className="flex items-center gap-1">
          <Kbd>E</Kbd> edit
        </span>
        <span className="flex items-center gap-1">
          <Kbd>R</Kbd> reject
        </span>
      </p>
      <ol className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2">
        {pending.map((proposal) => (
          <li key={proposal.proposal_id}>
            <ProposalCard
              proposal={proposal}
              clockMs={clockMs}
              selected={proposal.proposal_id === selectedId}
            />
          </li>
        ))}
      </ol>
      <footer className="flex shrink-0 gap-4 border-t border-line px-3 py-2.5 text-xs text-ink-3">
        <span>
          <span className="text-ink-2 tabular-nums">11</span> aired
        </span>
        <span>
          <span className="text-ink-2 tabular-nums">4</span> rejected
        </span>
        <span>
          <span className="text-ink-2 tabular-nums">2</span> expired
        </span>
      </footer>
    </Panel>
  );
}
