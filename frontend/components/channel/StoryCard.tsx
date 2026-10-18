"use client";

import { Receipt } from "@phosphor-icons/react/dist/ssr";
import { motion } from "motion/react";
import { useId } from "react";

import { Panel } from "@/components/ui/Panel";
import type { Channel, Cut, TableSwing } from "@/lib/contracts.generated";
import { DURATION, EASE } from "@/lib/motion";

const DECIDED_BY: Record<Cut["decided_by"], string> = {
  code: "Director",
  director: "Director agent",
  producer: "producer",
};

const REASON: Record<Cut["reason"], string> = {
  goal: "Goal",
  penalty: "Penalty",
  pressure: "Pressure",
  check_in: "Check-in",
  manual: "Producer's call",
  kickoff: "Start",
};

/**
 * Why the feed is where it is, at the top of the rail beside the picture: the cut's reason in
 * large type, what it means for this fan (on their own whip-around), what's at stake, the story
 * so far, and who wrote it and what checked it. Not a console panel: it is the page's headline.
 */
export function StoryCard({
  channel,
  fixtureOf,
  forWhom = null,
  className = "",
}: {
  channel: Channel;
  fixtureOf: (matchId: string) => string;
  /** On a fan's own whip-around: whose ("Westmere Athletic", "your XI"). */
  forWhom?: string | null;
  className?: string;
}) {
  const titleId = useId();
  const cut = channel.on_air;
  const {
    why,
    at_stake: atStake,
    story,
    claims,
    for_you: forYou,
  } = cut.package;
  const receipts = new Set(claims.flatMap((c) => c.evidence_event_ids)).size;
  return (
    <section
      aria-labelledby={titleId}
      className={`rounded-lg border border-line-strong bg-panel ${className}`}
    >
      <motion.div
        key={cut.cut_id}
        className="grid gap-4 p-4"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: DURATION.slow, ease: EASE.smoothOut }}
      >
        <header>
          <h2
            id={titleId}
            className="flex items-baseline justify-between gap-3 text-xs text-ink-3"
          >
            <span>Why we&rsquo;re here</span>
            <span className="font-mono tabular-nums">
              {REASON[cut.reason]} {minute(cut.clock_ms)}
            </span>
          </h2>
          <p className="mt-1 text-sm text-ink-2">{fixtureOf(cut.match_id)}</p>
          <p className="mt-2 text-xl leading-snug font-semibold text-balance text-ink">
            <Unbroken text={why} />
          </p>
        </header>
        {forWhom && forYou && (
          <div className="border-l-2 border-air pl-3">
            <h3 className="text-xs text-ink-3">For {forWhom}</h3>
            <p className="mt-0.5 text-base leading-snug text-ink">{forYou}</p>
          </div>
        )}
        {cut.package.storyline && (
          <div>
            <h3 className="text-xs text-ink-3">Storyline</h3>
            <p className="mt-0.5 text-sm text-ink">
              <Unbroken text={cut.package.storyline} />
            </p>
          </div>
        )}
        {atStake && (
          <div>
            <h3 className="text-xs text-ink-3">At stake</h3>
            <p className="mt-0.5 text-sm text-ink-2">{atStake}</p>
          </div>
        )}
        {cut.also_match_id && (
          <div>
            <h3 className="text-xs text-ink-3">
              Beside it: {fixtureOf(cut.also_match_id)}
            </h3>
            <p className="mt-0.5 text-sm text-ink-2">{cut.also_why}</p>
          </div>
        )}
        <div className="border-t border-line pt-3">
          <h3 className="text-xs text-ink-3">Story so far</h3>
          <p className="mt-1 text-sm text-ink-2">
            <Unbroken text={story} />
          </p>
        </div>
        <p className="flex items-center gap-1.5 text-xs text-ink-3">
          <Receipt size={14} className="shrink-0" />
          {receipts > 0
            ? credit(cut.package.written_by, receipts)
            : `Cut by the ${DECIDED_BY[cut.decided_by]}`}
        </p>
      </motion.div>
    </section>
  );
}

/** The cuts before this one, newest first: where the channel has been, and why. */
export function EarlierCuts({
  history,
  fixtureOf,
}: {
  history: Cut[];
  fixtureOf: (matchId: string) => string;
}) {
  return (
    <Panel title="Earlier cuts">
      {history.length ? (
        <ol className="max-h-64 overflow-y-auto px-3 py-2 text-sm">
          {history.map((c) => (
            <li
              key={c.cut_id}
              className="grid grid-cols-[3rem_minmax(0,1fr)] gap-x-2 py-1"
            >
              <span className="font-mono text-xs leading-5 text-ink-3 tabular-nums">
                {minute(c.clock_ms)}
              </span>
              <span className="text-ink-2">
                <span className="text-ink">{fixtureOf(c.match_id)}</span>
                <span className="block text-ink-3">{c.package.why}</span>
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="p-3 text-sm text-ink-3">
          Every cut the channel makes is listed here, with its reason.
        </p>
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

/** Who wrote the package, and what it was checked against. */
function credit(writtenBy: string[], receipts: number): string {
  const events = `${receipts} match ${receipts === 1 ? "event" : "events"}`;
  const agents = ["Watcher", "Director"].filter((a) =>
    writtenBy.includes(a.toLowerCase()),
  );
  if (!agents.length) return `Backed by ${events}`;
  const plural = agents.length > 1 ? "agents" : "agent";
  return `Written by the ${agents.join(" and ")} ${plural}, checked against ${events}`;
}

/** Text whose scorelines ("1-1") never break across lines. */
function Unbroken({ text }: { text: string }) {
  return text.split(/(\d+-\d+)/).map((part, i) =>
    i % 2 ? (
      <span key={i} className="whitespace-nowrap">
        {part}
      </span>
    ) : (
      part
    ),
  );
}

function minute(clockMs: number): string {
  return `${Math.floor(clockMs / 60_000) + 1}'`;
}
