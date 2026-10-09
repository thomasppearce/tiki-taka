"use client";

import { MotionConfig } from "motion/react";
import Link from "next/link";
import { useCallback, useMemo } from "react";

import { CrewLog } from "@/components/channel/CrewLog";
import { CutControls } from "@/components/channel/CutControls";
import {
  CutPackagePanel,
  TableMoves,
} from "@/components/channel/CutPackagePanel";
import { LeagueTable } from "@/components/channel/LeagueTable";
import { Multiview } from "@/components/channel/Multiview";
import { OnAirPanel } from "@/components/channel/OnAirPanel";
import { FeedState } from "@/components/match/FeedState";
import { SiteHeader } from "@/components/SiteHeader";
import { FEATURED_MATCH_ID } from "@/lib/api";
import type { MatchCard } from "@/lib/contracts.generated";
import { useChannel } from "@/lib/live/useChannel";
import { useMatchday } from "@/lib/live/useMatchday";
import { GUEST_PREFS, useFanPrefs, useRole } from "@/lib/role";

/**
 * Tiki-Taka: the final day as one channel. The Director cuts between the ten matches and says
 * why; the table moves as it stands; every match is a click away. The producer gets the cut
 * controls; viewers get the channel.
 */
export function ChannelPage() {
  const [role] = useRole();
  const [prefs] = useFanPrefs();
  const live = useChannel();
  const { matchday } = useMatchday();
  const producer = role === "producer";

  const cards = useMemo(
    () => matchday?.leagues.flatMap((l) => l.matches) ?? [],
    [matchday],
  );
  const byId = useMemo(
    () => new Map<string, MatchCard>(cards.map((c) => [c.match_id, c])),
    [cards],
  );
  const fixtureOf = useCallback(
    (matchId: string) => {
      const card = byId.get(matchId);
      return card ? `${card.home.name} v ${card.away.name}` : "";
    },
    [byId],
  );

  const { channel, table } = live;
  if (!channel)
    return (
      <div className="flex min-h-dvh flex-col bg-page">
        <SiteHeader />
        <FeedState status={live.status} what="the final day" />
      </div>
    );
  const view = role === "fan" ? prefs : GUEST_PREFS;
  const minute = Math.floor(channel.clock_ms / 60_000) + 1;

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-dvh flex-col bg-page">
        <SiteHeader>
          <p className="flex items-center gap-3 text-sm whitespace-nowrap">
            <span className="text-ink">Final day</span>
            <span className="hidden text-ink-3 sm:inline">Meridian League</span>
            <span className="font-mono text-ink-2 tabular-nums">{`${minute}'`}</span>
          </p>
        </SiteHeader>
        <main className="mx-auto grid w-full max-w-[1680px] flex-1 grid-cols-1 gap-3 p-3 xl:grid-cols-[minmax(0,1fr)_400px] xl:items-start">
          <div className="grid min-w-0 gap-3">
            {producer && (
              <CutControls
                channel={channel}
                controls={live.controls}
                fixtureOf={fixtureOf}
                serverClockMs={live.serverClockMs}
              />
            )}
            <OnAirPanel
              cut={channel.on_air}
              pending={
                channel.held || channel.pinned_match_id ? null : channel.pending
              }
              fixtureOf={fixtureOf}
              serverClockMs={live.serverClockMs}
              view={view}
            />
            <div className="grid min-w-0 gap-3 lg:grid-cols-2 lg:items-start">
              <CutPackagePanel channel={channel} fixtureOf={fixtureOf} />
              <TableMoves swings={table?.swings ?? []} />
            </div>
            <Multiview
              cards={cards}
              signals={live.signals}
              table={table}
              onAirMatchId={channel.on_air.match_id}
              pendingMatchId={channel.pending?.match_id ?? null}
              pinnedMatchId={channel.pinned_match_id}
              producer={producer}
              onCut={(id) => void live.controls.take(id)}
              onPin={(id) => void live.controls.pin(id)}
            />
            {producer && (
              <p className="text-sm text-ink-3">
                Graphics for the title decider are approved in its{" "}
                <Link
                  href={`/match/${FEATURED_MATCH_ID}`}
                  className="text-ink-2 underline decoration-line-strong underline-offset-4 hover:text-ink"
                >
                  control room
                </Link>
                .
              </p>
            )}
          </div>
          {/* The producer's column also holds the crew log, too tall to stay pinned. */}
          <aside
            className={`grid min-w-0 gap-3 ${producer ? "" : "xl:sticky xl:top-3"}`}
          >
            {table && (
              <LeagueTable
                table={table}
                cards={byId}
                onAirMatchId={channel.on_air.match_id}
              />
            )}
            {producer && <CrewLog channel={channel} fixtureOf={fixtureOf} />}
          </aside>
        </main>
      </div>
    </MotionConfig>
  );
}
