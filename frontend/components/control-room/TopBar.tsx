import { Broadcast } from "@phosphor-icons/react/dist/ssr";

import { ClubCrest } from "@/components/ClubCrest";
import { CLUBS, MATCH } from "@/lib/mock";

const FEEDS = [
  { id: "feed_analyst_en", audience: "Analyst", language: "EN" },
  { id: "feed_casual_es", audience: "Casual", language: "ES" },
];

/** Match context, feed profiles, and stream status. */
export function TopBar({
  clock,
  activeFeed,
}: {
  clock: string;
  activeFeed: string;
}) {
  return (
    <header className="flex h-12 shrink-0 items-center gap-6 border-b border-line bg-panel px-4">
      <p className="flex items-center gap-2 text-sm font-semibold text-ink">
        <Broadcast size={18} weight="bold" className="text-ink-2" />
        Match Desk
      </p>

      <div className="h-5 w-px bg-line" aria-hidden />

      <div className="flex items-center gap-3 text-sm">
        <span className="flex items-center gap-2 text-ink-2">
          <ClubCrest team="t_home" />
          {CLUBS.t_home.name}
        </span>
        <span className="flex items-center gap-1 font-mono text-xl leading-none font-semibold text-ink tabular-nums">
          <span className="sr-only">Score</span>
          {MATCH.score.t_home}
          <span className="text-ink-3">-</span>
          {MATCH.score.t_away}
        </span>
        <span className="flex items-center gap-2 text-ink-2">
          {CLUBS.t_away.name}
          <ClubCrest team="t_away" />
        </span>
        <span className="ml-2 font-mono text-ink tabular-nums">{clock}</span>
        <span className="text-xs text-ink-3">2nd half</span>
      </div>

      <span className="text-xs text-ink-3">Scenario: {MATCH.storyline}</span>

      <div className="ml-auto flex items-center gap-4">
        <div
          role="tablist"
          aria-label="Output feed"
          className="flex rounded-md border border-line p-0.5"
        >
          {FEEDS.map((feed) => {
            const active = feed.id === activeFeed;
            return (
              <button
                key={feed.id}
                type="button"
                role="tab"
                aria-selected={active}
                className={`flex h-7 items-center gap-1.5 rounded-[4px] px-2.5 text-label transition-[background-color,color] duration-150 ease-out focus-visible:outline-2 focus-visible:outline-air ${
                  active ? "bg-raised text-ink" : "text-ink-3 hover:text-ink-2"
                }`}
              >
                {feed.audience}
                <span className="font-mono text-xs text-ink-3">
                  {feed.language}
                </span>
              </button>
            );
          })}
        </div>
        <p className="flex items-center gap-2 text-xs text-ink-2">
          <span className="size-2 rounded-full bg-good" aria-hidden />
          Live
          <span className="font-mono text-ink-3">1x</span>
        </p>
      </div>
    </header>
  );
}
