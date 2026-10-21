import { SoccerBall } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";

import { ClubCrest } from "@/components/ClubCrest";
import { FeedTabs } from "@/components/control-room/FeedTabs";
import { MatchSwitcher } from "@/components/control-room/MatchSwitcher";
import { RoleSwitch } from "@/components/RoleSwitch";
import type { FeedId } from "@/lib/controlRoom";
import type { LiveStatus } from "@/lib/live/useLiveMatch";
import { type Side, club, useMatch } from "@/lib/match";

const STATUS: Record<LiveStatus, { label: string; dot: string }> = {
  live: { label: "Live", dot: "bg-good" },
  connecting: { label: "Connecting", dot: "bg-ink-3" },
  reconnecting: { label: "Reconnecting", dot: "bg-serious" },
  offline: { label: "Offline", dot: "bg-critical" },
};

/**
 * Match context, feed profiles, and stream status. Wraps to a second row on narrow screens;
 * full club names and the league appear only when there's room.
 */
export function TopBar({
  matchId,
  clock,
  period,
  score,
  status,
  feed,
  onFeedChange,
}: {
  matchId: string;
  clock: string;
  period: string;
  score: Record<Side, number>;
  status: LiveStatus;
  feed: FeedId;
  onFeedChange: (feed: FeedId) => void;
}) {
  const { leagueName } = useMatch();
  const { label, dot } = STATUS[status];
  return (
    <header className="flex min-h-12 shrink-0 flex-wrap items-center gap-x-6 gap-y-2 border-b border-line bg-panel px-4 py-2">
      <Link
        href="/"
        className="flex items-center gap-2 rounded-md text-sm font-semibold whitespace-nowrap text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-air"
      >
        <SoccerBall size={18} weight="bold" className="text-ink-2" />
        Tiki-Taka
      </Link>

      <div className="hidden h-5 w-px bg-line sm:block" aria-hidden />

      <div className="flex items-center gap-3 text-sm whitespace-nowrap">
        <ClubName side="home" />
        <span className="flex items-center gap-1 font-mono text-xl leading-none font-semibold text-ink tabular-nums">
          <span className="sr-only">Score</span>
          {score.home}
          <span className="text-ink-3">-</span>
          {score.away}
        </span>
        <ClubName side="away" crestFirst={false} />
        <span className="ml-2 font-mono text-ink tabular-nums">{clock}</span>
        <span className="hidden text-xs text-ink-3 md:inline">{period}</span>
      </div>

      <MatchSwitcher matchId={matchId} />

      <span className="hidden text-xs whitespace-nowrap text-ink-3 2xl:inline">
        {leagueName}
      </span>

      <div className="flex items-center gap-4 sm:ml-auto">
        <FeedTabs active={feed} onChange={onFeedChange} />
        <RoleSwitch />
        <p className="flex items-center gap-2 text-xs whitespace-nowrap text-ink-2">
          <span className={`size-2 rounded-full ${dot}`} aria-hidden />
          {label}
          <span className="font-mono text-ink-3">1x</span>
        </p>
      </div>
    </header>
  );
}

function ClubName({
  side,
  crestFirst = true,
}: {
  side: Side;
  crestFirst?: boolean;
}) {
  const { name, short } = club(useMatch(), side);
  return (
    <span className="flex items-center gap-2 text-ink-2">
      {crestFirst && <ClubCrest side={side} />}
      <span className="hidden xl:inline">{name}</span>
      <span className="xl:hidden">{short}</span>
      {!crestFirst && <ClubCrest side={side} />}
    </span>
  );
}
