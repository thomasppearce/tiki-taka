"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import type { MatchCard } from "@/lib/contracts.generated";
import { useMatchday } from "@/lib/live/useMatchday";

function minuteOf(card: MatchCard): string {
  return card.status === "full_time"
    ? "FT"
    : `${Math.floor(card.clock_ms / 60_000) + 1}'`;
}

function useCards(): MatchCard[] {
  const { matchday } = useMatchday();
  return matchday?.leagues.flatMap((league) => league.matches) ?? [];
}

/** Every match of the day, to take the control room to another: a finished match is never a
 * dead end. */
export function MatchSwitcher({ matchId }: { matchId: string }) {
  const router = useRouter();
  const cards = useCards();
  if (!cards.length) return null;
  return (
    <label className="flex items-center text-xs text-ink-3">
      <span className="sr-only">Go to another match</span>
      <select
        value={matchId}
        onChange={(e) => router.push(`/match/${e.target.value}/`)}
        className="h-7 max-w-60 rounded-md border border-line bg-page px-2 text-label text-ink transition-[border-color] duration-(--duration-quick) hover:border-line-strong focus-visible:border-air focus-visible:outline-none"
      >
        {cards.map((card) => (
          <option key={card.match_id} value={card.match_id}>
            {`${card.home.short} ${card.score_home}-${card.score_away} ${card.away.short} · ${minuteOf(card)}`}
          </option>
        ))}
      </select>
    </label>
  );
}

/** At full time: the matches still playing, one click away. */
export function StillPlaying({ matchId }: { matchId: string }) {
  const live = useCards().filter(
    (card) => card.match_id !== matchId && card.status !== "full_time",
  );
  return (
    <div className="flex flex-col items-center gap-3 text-center">
      <p>Full time here.</p>
      {live.length > 0 ? (
        <>
          <p className="text-xs">Still playing:</p>
          <ul className="flex flex-wrap justify-center gap-2">
            {live.map((card) => (
              <li key={card.match_id}>
                <Link
                  href={`/match/${card.match_id}/`}
                  className="inline-flex h-7 items-center gap-2 rounded-md border border-line px-2 text-label text-ink transition-[border-color] duration-(--duration-quick) hover:border-line-strong focus-visible:outline-2 focus-visible:outline-air"
                >
                  {`${card.home.short} ${card.score_home}-${card.score_away} ${card.away.short}`}
                  <span className="font-mono text-ink-3">{minuteOf(card)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="text-xs">
          Every match is over:{" "}
          <Link
            href="/recap/"
            className="text-ink-2 underline decoration-line-strong underline-offset-4 hover:text-ink"
          >
            how the matchday unfolded
          </Link>
          .
        </p>
      )}
    </div>
  );
}
