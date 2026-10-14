"use client";

import { ArrowRight } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";

import { MatchCard, Status, statusText } from "@/components/centre/MatchCard";
import { MomentumRibbon } from "@/components/centre/MomentumRibbon";
import { Crest } from "@/components/Crest";
import { FeedState } from "@/components/match/FeedState";
import { SiteHeader } from "@/components/SiteHeader";
import type { MatchCard as Card } from "@/lib/contracts.generated";
import { useMatchday } from "@/lib/live/useMatchday";
import { useRole } from "@/lib/role";

/**
 * The match centre: today's fixtures in three fictional leagues, live. The featured match (the
 * one the full agent team covers) leads; every card opens its match page.
 */
export function MatchCentre() {
  const { matchday, status } = useMatchday();
  if (!matchday)
    return (
      <div className="flex min-h-dvh flex-col bg-page">
        <SiteHeader />
        <FeedState
          status={status === "offline" ? "offline" : "connecting"}
          what="the matchday"
        />
      </div>
    );

  const cards = matchday.leagues.flatMap((league) => league.matches);
  const featured = cards.find((card) => card.featured);
  const live = cards.filter((card) => card.status === "live").length;

  return (
    <div className="flex min-h-dvh flex-col bg-page">
      <SiteHeader>
        <p className="flex items-center gap-2 text-xs whitespace-nowrap text-ink-2">
          <span
            className={`size-2 rounded-full ${status === "offline" ? "bg-critical" : "bg-good"}`}
            aria-hidden
          />
          {status === "offline" ? "Reconnecting" : `${live} live`}
          <span className="text-ink-3">of {cards.length} matches</span>
        </p>
      </SiteHeader>
      <main className="mx-auto flex w-full max-w-[1400px] flex-1 flex-col gap-8 px-4 py-6">
        <div className="flex max-w-[70ch] flex-col gap-2">
          <h1 className="text-xl font-semibold text-ink">
            {matchdayLabel(matchday)}
          </h1>
          <p className="text-sm text-ink-2">
            {matchday.last_matchday
              ? "The last day of the Meridian League season: ten matches at once, with the title, the top four, and the drop decided today."
              : `Matchday ${matchday.matchday_number} of the Meridian League: ten matches at once, and the table moves with every goal.`}{" "}
            The featured match has the full AI agent team proposing graphics,
            each with the events that justify it, and a human producer deciding
            what goes on air.
          </p>
        </div>
        {featured && <Featured card={featured} />}
        {matchday.leagues.map((league) => (
          <section
            key={league.league_id}
            aria-labelledby={league.league_id}
            className="flex flex-col gap-3"
          >
            <h2
              id={league.league_id}
              className="text-label font-medium text-ink-2"
            >
              {league.name}
            </h2>
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {league.matches.map((card) => (
                <li key={card.match_id} className="min-w-0">
                  <MatchCard card={card} />
                </li>
              ))}
            </ul>
          </section>
        ))}
      </main>
    </div>
  );
}

function Featured({ card }: { card: Card }) {
  const [role] = useRole();
  const minute = (ms: number) => `${Math.floor(ms / 60_000) + 1}'`;
  return (
    <section
      aria-label={`Featured match: ${card.home.name} ${card.score_home}, ${card.away.name} ${card.score_away}, ${statusText(card)}`}
      className="grid gap-6 rounded-lg border border-line bg-panel p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] lg:items-center"
    >
      <div className="flex min-w-0 flex-col gap-5">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <Status card={card} />
          <span className="text-ink-3">
            Featured · {card.league_name} · Full agent coverage
          </span>
        </div>
        <div className="flex items-center gap-4">
          <Side club={card.home} />
          <p className="font-mono text-4xl leading-none font-semibold whitespace-nowrap text-ink tabular-nums">
            {card.score_home}
            <span className="px-2 text-ink-3">-</span>
            {card.score_away}
          </p>
          <Side club={card.away} alignEnd />
        </div>
        {card.top_moment && (
          <p className="text-sm text-ink-2">
            <span className="text-ink-3">Defining moment so far </span>
            {card.top_moment.label} ({minute(card.top_moment.match_clock_ms)})
          </p>
        )}
        <Link
          href={`/match/${card.match_id}`}
          className="inline-flex h-9 w-fit items-center gap-2 rounded-md border border-air bg-air px-3 text-sm font-medium text-ink-on-fill transition-[background-color,border-color] duration-150 ease-out hover:border-air-hover hover:bg-air-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-air active:translate-y-px"
        >
          {role === "producer" ? "Open the control room" : "Watch live"}
          <ArrowRight size={16} weight="bold" />
        </Link>
      </div>
      <div className="flex min-w-0 flex-col gap-2">
        <MomentumRibbon momentum={card.momentum} height={96} />
        <div className="flex justify-between font-mono text-xs text-ink-3">
          <span>0&apos;</span>
          <span>45&apos;</span>
          <span>90&apos;</span>
        </div>
        <ul className="flex gap-4 text-xs text-ink-3">
          <li className="flex items-center gap-1.5">
            <span className="h-2 w-3 rounded-[2px] bg-home/70" aria-hidden />
            {card.home.short} on top
          </li>
          <li className="flex items-center gap-1.5">
            <span className="h-2 w-3 rounded-[2px] bg-away/70" aria-hidden />
            {card.away.short} on top
          </li>
        </ul>
      </div>
    </section>
  );
}

function Side({
  club,
  alignEnd = false,
}: {
  club: Card["home"];
  alignEnd?: boolean;
}) {
  return (
    <div
      className={`flex min-w-0 flex-1 items-center gap-3 ${alignEnd ? "flex-row-reverse text-right" : ""}`}
    >
      <Crest club={club} size={40} />
      <div className="min-w-0">
        <p className="truncate text-base font-medium text-ink">{club.name}</p>
        <p className="font-mono text-xs text-ink-3">{club.short}</p>
      </div>
    </div>
  );
}

/** "Matchday 38 · Final day" on the season's last, "Matchday 12" otherwise. */
export function matchdayLabel(day: {
  matchday_number: number;
  last_matchday: boolean;
}): string {
  return `Matchday ${day.matchday_number}${day.last_matchday ? " · Final day" : ""}`;
}
