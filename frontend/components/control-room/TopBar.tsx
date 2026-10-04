import { Broadcast } from "@phosphor-icons/react/dist/ssr";

import { ClubCrest } from "@/components/ClubCrest";
import { FeedTabs } from "@/components/control-room/FeedTabs";
import type { FeedId } from "@/lib/controlRoom";
import { CLUBS, MATCH, type TeamId } from "@/lib/mock";

/**
 * Match context, feed profiles, and stream status. Wraps to a second row on narrow screens;
 * full club names and the scenario label appear only when there's room.
 */
export function TopBar({
  clock,
  feed,
  onFeedChange,
}: {
  clock: string;
  feed: FeedId;
  onFeedChange: (feed: FeedId) => void;
}) {
  return (
    <header className="flex min-h-12 shrink-0 flex-wrap items-center gap-x-6 gap-y-2 border-b border-line bg-panel px-4 py-2">
      <p className="flex items-center gap-2 text-sm font-semibold whitespace-nowrap text-ink">
        <Broadcast size={18} weight="bold" className="text-ink-2" />
        Match Desk
      </p>

      <div className="hidden h-5 w-px bg-line sm:block" aria-hidden />

      <div className="flex items-center gap-3 text-sm whitespace-nowrap">
        <ClubName team="t_home" />
        <span className="flex items-center gap-1 font-mono text-xl leading-none font-semibold text-ink tabular-nums">
          <span className="sr-only">Score</span>
          {MATCH.score.t_home}
          <span className="text-ink-3">-</span>
          {MATCH.score.t_away}
        </span>
        <ClubName team="t_away" crestFirst={false} />
        <span className="ml-2 font-mono text-ink tabular-nums">{clock}</span>
        <span className="hidden text-xs text-ink-3 md:inline">2nd half</span>
      </div>

      <span className="hidden text-xs whitespace-nowrap text-ink-3 2xl:inline">
        Scenario: {MATCH.storyline}
      </span>

      <div className="flex items-center gap-4 sm:ml-auto">
        <FeedTabs active={feed} onChange={onFeedChange} />
        <p className="flex items-center gap-2 text-xs whitespace-nowrap text-ink-2">
          <span className="size-2 rounded-full bg-good" aria-hidden />
          Live
          <span className="font-mono text-ink-3">1x</span>
        </p>
      </div>
    </header>
  );
}

function ClubName({
  team,
  crestFirst = true,
}: {
  team: TeamId;
  crestFirst?: boolean;
}) {
  const club = CLUBS[team];
  return (
    <span className="flex items-center gap-2 text-ink-2">
      {crestFirst && <ClubCrest team={team} />}
      <span className="hidden xl:inline">{club.name}</span>
      <span className="xl:hidden">{club.short}</span>
      {!crestFirst && <ClubCrest team={team} />}
    </span>
  );
}
