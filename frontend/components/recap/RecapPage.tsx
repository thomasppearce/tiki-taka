"use client";

import Link from "next/link";
import { MotionConfig } from "motion/react";
import { useCallback } from "react";

import { MatchdayRecap } from "@/components/channel/MatchdayRecap";
import { Crest } from "@/components/Crest";
import { FeedState } from "@/components/match/FeedState";
import { MatchRecapCard } from "@/components/recap/MatchRecapCard";
import { SiteHeader } from "@/components/SiteHeader";
import type { MatchRecap } from "@/lib/contracts.generated";
import { useMatchRecaps, useRecap } from "@/lib/live/useRecap";

/**
 * How the matchday ends, on demand: the day's recap and every match's, whatever the live clock
 * says (it gives the results away). For anyone who can't wait for the final whistle, judges
 * included; the live channel is unaffected.
 */
export function RecapPage() {
  const recap = useRecap(true);
  const matches = useMatchRecaps(true);
  const fixtureOf = useCallback(
    (matchId: string) => {
      const m = matches?.find((r) => r.match_id === matchId);
      return m ? `${m.home.name} v ${m.away.name}` : "";
    },
    [matches],
  );
  if (!recap || !matches)
    return (
      <div className="flex min-h-dvh flex-col bg-page">
        <SiteHeader />
        <FeedState status="connecting" what="the recap" />
      </div>
    );
  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-dvh flex-col bg-page">
        <SiteHeader>
          <p className="text-sm whitespace-nowrap text-ink">
            Recap
            {recap.matchday ? (
              <span className="ml-3 text-ink-3">Matchday {recap.matchday}</span>
            ) : null}
          </p>
        </SiteHeader>
        <main className="mx-auto grid w-full max-w-[1200px] flex-1 gap-3 p-3">
          <p className="text-sm text-ink-3">
            How the matchday ends, so it gives the results away. Rather watch it
            unfold?{" "}
            <Link
              href="/"
              className="text-ink-2 underline decoration-line-strong underline-offset-4 hover:text-ink"
            >
              Back to the live channel
            </Link>
            .
          </p>
          {recap.status !== "pending" && (
            <MatchdayRecap recap={recap} fixtureOf={fixtureOf} />
          )}
          <h2 className="mt-3 text-sm font-medium text-ink">Every match</h2>
          <ul className="grid gap-3 md:grid-cols-2">
            {matches.map((m) => (
              <li key={m.match_id} className="grid">
                <MatchRecapCard recap={m} heading={<Fixture recap={m} />} />
              </li>
            ))}
          </ul>
        </main>
      </div>
    </MotionConfig>
  );
}

/** The fixture as a card's heading: crests, names, and the final score; a link to the match. */
function Fixture({ recap }: { recap: MatchRecap }) {
  return (
    <Link
      href={`/match/${recap.match_id}`}
      className="flex items-center gap-2 rounded-sm text-xs text-ink-3 hover:text-ink-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-air"
    >
      <Crest club={recap.home} size={16} />
      <span className="truncate">{recap.home.name}</span>
      <span className="font-mono text-ink-2 tabular-nums">
        {recap.score_home}-{recap.score_away}
      </span>
      <span className="truncate">{recap.away.name}</span>
      <Crest club={recap.away} size={16} />
      <span className="ml-1 shrink-0">&middot; Full time</span>
    </Link>
  );
}
