import { Broadcast } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";

import { MomentumRibbon } from "@/components/centre/MomentumRibbon";
import { Crest } from "@/components/Crest";
import type { ClubRef, MatchCard as Card } from "@/lib/contracts.generated";

/** One fixture in the match centre: score, clock, momentum so far, and its defining moment. */
export function MatchCard({ card }: { card: Card }) {
  const leader =
    card.score_home === card.score_away
      ? null
      : card.score_home > card.score_away
        ? "home"
        : "away";
  return (
    <Link
      href={`/match/${card.match_id}`}
      aria-label={`${card.home.name} ${card.score_home}, ${card.away.name} ${card.score_away}, ${statusText(card)}`}
      className="flex min-w-0 flex-col gap-3 rounded-lg border border-line bg-panel p-3 transition-[background-color,border-color] duration-150 ease-out hover:border-line-strong hover:bg-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-air"
    >
      <div className="flex items-center justify-between gap-2 text-xs">
        <Status card={card} />
        {card.featured && (
          <span className="flex items-center gap-1 text-ink-2">
            <Broadcast size={14} weight="bold" />
            Agent coverage
          </span>
        )}
      </div>
      <div className="flex flex-col gap-1.5">
        <TeamRow
          club={card.home}
          score={card.score_home}
          lead={leader === "home"}
        />
        <TeamRow
          club={card.away}
          score={card.score_away}
          lead={leader === "away"}
        />
      </div>
      <MomentumRibbon momentum={card.momentum} />
      <p className="truncate text-xs text-ink-3">
        {card.top_moment
          ? `${card.top_moment.label} · ${Math.floor(card.top_moment.match_clock_ms / 60_000) + 1}'`
          : "No defining moments yet"}
      </p>
    </Link>
  );
}

function TeamRow({
  club,
  score,
  lead,
}: {
  club: ClubRef;
  score: number;
  lead: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <Crest club={club} size={22} />
      <span
        className={`min-w-0 flex-1 truncate text-sm ${lead ? "font-medium text-ink" : "text-ink-2"}`}
      >
        {club.name}
      </span>
      <span
        className={`font-mono text-base tabular-nums ${lead ? "font-semibold text-ink" : "text-ink-2"}`}
      >
        {score}
      </span>
    </div>
  );
}

export function Status({ card }: { card: Card }) {
  if (card.status === "full_time")
    return <span className="font-medium text-ink-3">Full time</span>;
  return (
    <span className="flex items-center gap-1.5 font-medium text-ink-2">
      <span className="size-1.5 rounded-full bg-good" aria-hidden />
      Live
      <span className="font-mono text-ink tabular-nums">
        {Math.floor(card.clock_ms / 60_000) + 1}&apos;
      </span>
    </span>
  );
}

export function statusText(card: Card): string {
  return card.status === "full_time"
    ? "full time"
    : `live, minute ${Math.floor(card.clock_ms / 60_000) + 1}`;
}
