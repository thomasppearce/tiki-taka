"use client";

import { Receipt } from "@phosphor-icons/react/dist/ssr";
import { motion } from "motion/react";
import { type ReactNode, useId } from "react";

import type { MatchRecap } from "@/lib/contracts.generated";
import { DURATION, EASE } from "@/lib/motion";

/**
 * One match's recap at its final whistle: its Watcher's headline and story, and who wrote and
 * checked it. `heading` replaces the default eyebrow (the /recap page puts the fixture there).
 */
export function MatchRecapCard({
  recap,
  heading,
  className = "",
}: {
  recap: MatchRecap;
  heading?: ReactNode;
  className?: string;
}) {
  const titleId = useId();
  if (recap.status === "pending") return null;
  if (recap.status === "writing") {
    const text = "The Watcher is writing this match's recap";
    return (
      <section
        role="status"
        className={`rounded-lg border border-line bg-panel px-4 py-3 ${className}`}
      >
        {heading ?? <p className="text-xs text-ink-3">Full time</p>}
        <p className="t-think-text mt-1 text-sm text-ink" data-text={text}>
          {text}
        </p>
      </section>
    );
  }
  const receipts = new Set(recap.claims.flatMap((c) => c.evidence_event_ids))
    .size;
  return (
    <section
      aria-labelledby={titleId}
      className={`rounded-lg border border-line-strong bg-panel ${className}`}
    >
      <motion.div
        className="grid gap-2 p-4"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: DURATION.slow, ease: EASE.smoothOut }}
      >
        {heading ?? (
          <p className="text-xs text-ink-3">Full time &middot; Match recap</p>
        )}
        <h2
          id={titleId}
          className="text-lg leading-snug font-semibold text-balance text-ink"
        >
          {recap.headline}
        </h2>
        <p className="max-w-[65ch] text-sm leading-relaxed text-ink-2">
          {recap.story}
        </p>
        <p className="mt-1 flex items-center gap-1.5 text-xs text-ink-3">
          <Receipt size={14} className="shrink-0" />
          {recap.written_by === "agents"
            ? `Written by this match's Watcher on Microsoft Foundry; cites ${receipts} ${receipts === 1 ? "event" : "events"}, checked by code and the fact-checker.`
            : "Written by code from the match's goals."}
        </p>
      </motion.div>
    </section>
  );
}
