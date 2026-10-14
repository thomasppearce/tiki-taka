"use client";

import { Receipt } from "@phosphor-icons/react/dist/ssr";
import { motion } from "motion/react";
import { useId } from "react";

import { Crest } from "@/components/Crest";
import type { ClubRef, Recap, RecapFact } from "@/lib/contracts.generated";
import { DURATION, EASE } from "@/lib/motion";

/**
 * How the final day unfolded, once the last match ends: the recap writer's headline and story,
 * the four outcomes code worked out (the title, the top four, the drop, the Golden Boot), and the
 * moments that decided the day, each with its receipt: the code's own line for the goal it cites.
 */
export function FinalDayRecap({
  recap,
  fixtureOf,
}: {
  recap: Recap;
  fixtureOf: (matchId: string) => string;
}) {
  const titleId = useId();
  if (recap.status === "writing") {
    const text = "The recap writer is telling the story of the day";
    return (
      <section
        role="status"
        className="rounded-lg border border-line-strong bg-panel px-4 py-3"
      >
        <p className="text-xs text-ink-3">Full time</p>
        <p className="t-think-text mt-1 text-sm text-ink" data-text={text}>
          {text}
        </p>
      </section>
    );
  }
  const facts = new Map(recap.facts.map((f) => [f.fact_id, f]));
  const cited = new Set(recap.beats.flatMap((b) => b.fact_ids)).size;
  return (
    <section
      aria-labelledby={titleId}
      className="rounded-lg border border-line-strong bg-panel"
    >
      <motion.div
        className="grid gap-5 p-4 sm:p-5"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: DURATION.slow, ease: EASE.smoothOut }}
      >
        <header className="max-w-[70ch]">
          <p className="text-xs text-ink-3">
            Full time &middot; How the final day unfolded
          </p>
          <h2
            id={titleId}
            className="mt-1.5 text-2xl leading-tight font-semibold text-balance text-ink sm:text-3xl"
          >
            {recap.headline}
          </h2>
          <p className="mt-2 text-base leading-relaxed text-ink-2">
            {recap.standfirst}
          </p>
        </header>

        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-line bg-line lg:grid-cols-4">
          <Outcome label="Champions">
            {recap.champions && <Club club={recap.champions} />}
          </Outcome>
          <Outcome label="Top four">
            <Clubs clubs={recap.top_four} />
          </Outcome>
          <Outcome label="Relegated">
            <Clubs clubs={recap.relegated} />
          </Outcome>
          <Outcome label="Golden Boot">
            {recap.golden_boot && (
              <span className="flex items-center gap-2">
                <Crest club={recap.golden_boot.club} size={20} />
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-ink">
                    {recap.golden_boot.name}
                  </span>
                  <span className="block text-xs text-ink-3 tabular-nums">
                    {recap.golden_boot.goals} league goals
                  </span>
                </span>
              </span>
            )}
          </Outcome>
        </dl>

        <ol className="grid gap-0">
          {recap.beats.map((beat, i) => (
            <motion.li
              key={`${beat.minute}-${i}`}
              className="grid grid-cols-[3rem_minmax(0,1fr)] gap-x-3 border-t border-line py-3 first:border-t-0 first:pt-0"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: DURATION.slow,
                ease: EASE.smoothOut,
                delay: 0.08 + i * 0.05,
              }}
            >
              <span className="pt-0.5 font-mono text-sm text-ink-3 tabular-nums">
                {`${beat.minute}'`}
              </span>
              <span>
                {beat.match_id && (
                  <span className="block text-xs text-ink-3">
                    {fixtureOf(beat.match_id)}
                  </span>
                )}
                <span className="mt-0.5 block text-sm leading-snug text-ink">
                  {beat.text}
                </span>
                {beat.fact_ids
                  .map((id) => facts.get(id))
                  .filter((f): f is RecapFact => f?.minute != null)
                  .map((f) => (
                    <span
                      key={f.fact_id}
                      className="mt-1 flex items-start gap-1.5 text-xs text-ink-3"
                    >
                      <Receipt size={12} className="mt-0.5 shrink-0" />
                      {receipt(f)}
                    </span>
                  ))}
              </span>
            </motion.li>
          ))}
        </ol>

        <footer className="grid gap-1.5 border-t border-line pt-3 text-xs text-ink-3">
          <p className="flex items-center gap-1.5">
            <Receipt size={14} className="shrink-0" />
            {recap.written_by === "agents"
              ? `Written by the recap writer on Microsoft Foundry; every beat cites the code's facts (${cited}), checked by code and by the fact-checker.`
              : "Written by code from the day's facts."}
          </p>
          {recap.checks.length > 0 && (
            <details>
              <summary className="cursor-pointer text-ink-3 hover:text-ink-2">
                Sent back on the way ({recap.checks.length})
              </summary>
              <ul className="mt-1 grid gap-1 pl-5">
                {recap.checks.map((check) => (
                  <li key={check} className="list-disc">
                    {check}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </footer>
      </motion.div>
    </section>
  );
}

function Outcome({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-panel px-3 py-2.5">
      <dt className="text-xs text-ink-3">{label}</dt>
      <dd className="mt-1.5">{children}</dd>
    </div>
  );
}

function Club({ club }: { club: ClubRef }) {
  return (
    <span className="flex items-center gap-2">
      <Crest club={club} size={20} />
      <span className="truncate text-sm font-medium text-ink">{club.name}</span>
    </span>
  );
}

function Clubs({ clubs }: { clubs: ClubRef[] }) {
  return (
    <ul className="grid gap-1">
      {clubs.map((club) => (
        <li key={club.club_id} className="flex items-center gap-2">
          <Crest club={club} size={16} />
          <span className="truncate text-sm text-ink-2">{club.name}</span>
        </li>
      ))}
    </ul>
  );
}

/** The code's line for a goal, without its minute (the beat's) or what it did to the table
 * (the beat says that). */
function receipt(fact: RecapFact): string {
  return fact.text.split(". ")[0].replace(/^\d+' /, "");
}
