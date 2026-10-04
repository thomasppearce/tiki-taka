"use client";

import { AnimatePresence, motion } from "motion/react";

import {
  type CardActions,
  ProposalCard,
} from "@/components/control-room/ProposalCard";
import { Kbd } from "@/components/ui/Kbd";
import { Panel } from "@/components/ui/Panel";
import type { Proposal } from "@/lib/contracts.generated";
import type { FeedId, State } from "@/lib/controlRoom";
import { DURATION, EASE } from "@/lib/motion";

type Decisions = State["decisions"];

// Each exit says what happened: approved cards head left toward the program monitor, rejected
// ones shrink away, expired ones just fade.
const EXIT = {
  approved: {
    opacity: 0,
    x: -32,
    transition: { duration: DURATION.fast, ease: EASE.smoothOut },
  },
  rejected: {
    opacity: 0,
    scale: 0.96,
    transition: { duration: DURATION.quick, ease: EASE.inOut },
  },
  expired: {
    opacity: 0,
    transition: { duration: DURATION.medium, ease: EASE.inOut },
  },
};

/** The producer's queue: pending proposals, highest priority first. */
export function ProposalQueue({
  proposals,
  selectedId,
  editingId,
  clockMs,
  feed,
  decisions,
  counts,
  actions,
  className,
}: {
  proposals: Proposal[];
  selectedId: string | null;
  editingId: string | null;
  clockMs: number;
  feed: FeedId;
  decisions: Decisions;
  counts: State["counts"];
  actions: CardActions;
  className?: string;
}) {
  return (
    <Panel
      title="Proposals"
      aside={
        <span className="text-xs text-ink-3 tabular-nums">
          {proposals.length} pending
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
        <AnimatePresence initial={false} custom={decisions}>
          {proposals.map((proposal) => {
            const id = proposal.proposal_id;
            return (
              <motion.li
                key={id}
                layout
                custom={decisions}
                variants={{
                  enter: { opacity: 0, y: -12 },
                  rest: { opacity: 1, y: 0, x: 0, scale: 1 },
                  exit: (d: Decisions) => EXIT[d[id] ?? "expired"],
                }}
                initial="enter"
                animate="rest"
                exit="exit"
                transition={{
                  duration: DURATION.fast,
                  ease: EASE.smoothOut,
                  layout: { duration: DURATION.fast, ease: EASE.smoothOut },
                }}
              >
                <ProposalCard
                  proposal={proposal}
                  clockMs={clockMs}
                  feed={feed}
                  selected={id === selectedId}
                  editing={id === editingId}
                  actions={actions}
                />
              </motion.li>
            );
          })}
        </AnimatePresence>
        {proposals.length === 0 && (
          <li className="flex flex-1 items-center justify-center p-6 text-center text-sm text-ink-3">
            Queue clear. The agents will propose the next moment as it happens.
          </li>
        )}
      </ol>
      <footer className="flex shrink-0 gap-4 border-t border-line px-3 py-2.5 text-xs text-ink-3">
        <span>
          <span className="text-ink-2 tabular-nums">{counts.aired}</span> aired
        </span>
        <span>
          <span className="text-ink-2 tabular-nums">{counts.rejected}</span>{" "}
          rejected
        </span>
        <span>
          <span className="text-ink-2 tabular-nums">{counts.expired}</span>{" "}
          expired
        </span>
      </footer>
    </Panel>
  );
}
