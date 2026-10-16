"use client";

import { MotionConfig } from "motion/react";
import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { matchdayLabel } from "@/components/centre/MatchCentre";
import { CrewLog } from "@/components/channel/CrewLog";
import { MatchdayRecap } from "@/components/channel/MatchdayRecap";
import { CutControls } from "@/components/channel/CutControls";
import { FantasyXi } from "@/components/channel/FantasyXi";
import { GoldenBoot } from "@/components/channel/GoldenBoot";
import { LeagueTable } from "@/components/channel/LeagueTable";
import { Multiview } from "@/components/channel/Multiview";
import { OnAirPanel } from "@/components/channel/OnAirPanel";
import {
  EarlierCuts,
  StoryCard,
  TableMoves,
} from "@/components/channel/StoryCard";
import { WhipControls, WhipNudge } from "@/components/channel/WhipControls";
import { XiPicker } from "@/components/channel/XiPicker";
import { FeedState } from "@/components/match/FeedState";
import { SiteHeader } from "@/components/SiteHeader";
import { FEATURED_MATCH_ID } from "@/lib/api";
import type {
  Channel,
  ClubRef,
  MatchCard,
  MatchSignal,
} from "@/lib/contracts.generated";
import { useChannel } from "@/lib/live/useChannel";
import { useMatchday } from "@/lib/live/useMatchday";
import { useSquads } from "@/lib/live/useSquads";
import { useMatchRecaps, useRecap } from "@/lib/live/useRecap";
import { GUEST_PREFS, useFanPrefs, useRole } from "@/lib/role";
import { lensOf, useWhip } from "@/lib/whip";

/**
 * Tiki-Taka: a matchday as one channel (the demo's is the season's last). The Director cuts between the ten matches and says
 * why; the table moves as it stands; every match is a click away. The producer gets the cut
 * controls; guests get the channel; a signed-in fan can make it their own, cut by what matters
 * to their club or by their fantasy XI.
 */
export function ChannelPage() {
  const [role] = useRole();
  const [prefs] = useFanPrefs();
  const [whip, setWhip] = useWhip();
  const fan = role === "fan";
  const producer = role === "producer";
  const lens = fan ? lensOf(whip) : null;
  const live = useChannel(lens);
  const { matchday } = useMatchday();
  const squads = useSquads();
  const recap = useRecap();
  const matchRecaps = useMatchRecaps();
  const recapHeadlines = useMemo(
    () =>
      new Map(
        (matchRecaps ?? [])
          .filter((r) => r.headline)
          .map((r) => [r.match_id, r.headline ?? ""]),
      ),
    [matchRecaps],
  );
  const [picking, setPicking] = useState(false);

  const cards = useMemo(
    () => matchday?.leagues.flatMap((l) => l.matches) ?? [],
    [matchday],
  );
  const byId = useMemo(
    () => new Map<string, MatchCard>(cards.map((c) => [c.match_id, c])),
    [cards],
  );
  const clubs = useMemo(
    () =>
      new Map<string, ClubRef>(
        cards.flatMap((c) => [
          [c.home.club_id, c.home],
          [c.away.club_id, c.away],
        ]),
      ),
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
  const picker = fan && squads && (
    <XiPicker
      open={picking}
      squads={squads}
      clubs={clubs}
      initial={whip.xi}
      onClose={() => setPicking(false)}
      onSave={(xi) => {
        setWhip({ ...whip, mode: "fantasy", xi });
        setPicking(false);
      }}
    />
  );
  if (!channel)
    return (
      <div className="flex min-h-dvh flex-col bg-page">
        <SiteHeader />
        <FeedState status={live.status} what="the matchday" />
        {picker}
      </div>
    );
  const view = fan ? prefs : GUEST_PREFS;
  const minute = Math.floor(channel.clock_ms / 60_000) + 1;
  const own = channel.lens.kind !== "channel"; // a fan's own whip-around: theirs to steer
  const fanClub = channel.lens.club_id ? clubs.get(channel.lens.club_id) : null;
  const forWhom =
    channel.lens.kind === "club"
      ? (fanClub?.name ?? null)
      : channel.lens.kind === "fantasy"
        ? "your XI"
        : null;

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-dvh flex-col bg-page">
        <SiteHeader>
          <p className="flex items-center gap-3 text-sm whitespace-nowrap">
            <span className="text-ink">
              {table ? matchdayLabel(table) : "Matchday"}
            </span>
            <span className="hidden text-ink-3 sm:inline">Meridian League</span>
            <span className="font-mono text-ink-2 tabular-nums">{`${minute}'`}</span>
          </p>
        </SiteHeader>
        <main className="mx-auto grid w-full max-w-[1680px] flex-1 grid-cols-1 gap-3 p-3 xl:grid-cols-[minmax(0,1fr)_400px] xl:items-start">
          <div className="grid min-w-0 gap-3">
            {recap && recap.status !== "pending" && (
              <MatchdayRecap recap={recap} fixtureOf={fixtureOf} />
            )}
            {producer && (
              <CutControls
                channel={channel}
                controls={live.controls}
                fixtureOf={fixtureOf}
                serverClockMs={live.serverClockMs}
              />
            )}
            {fan && (
              <WhipControls
                whip={whip}
                setWhip={setWhip}
                clubs={clubs}
                lens={channel.lens}
                onEditXi={() => setPicking(true)}
              />
            )}
            {role === "guest" && <WhipNudge />}
            <OnAirPanel
              cut={channel.on_air}
              pending={
                channel.held || channel.pinned_match_id ? null : channel.pending
              }
              fixtureOf={fixtureOf}
              serverClockMs={live.serverClockMs}
              view={view}
              title={own ? `Your whip-around: ${forWhom}` : "On air"}
              forWhom={forWhom}
              lens={channel.lens}
            />
            {/* Below xl the rail stacks under everything: tell the story right here. */}
            <StoryCard
              channel={channel}
              fixtureOf={fixtureOf}
              forWhom={forWhom}
              className="xl:hidden"
            />
            <Multiview
              cards={cards}
              signals={live.signals}
              table={table}
              onAirMatchId={channel.on_air.match_id}
              pendingMatchId={channel.pending?.match_id ?? null}
              pinnedMatchId={channel.pinned_match_id}
              canCut={producer || own}
              tags={tagsFor(channel, live.signals)}
              recaps={recapHeadlines}
              onCut={(id) => void live.controls.take(id)}
              onPin={(id) => void live.controls.pin(id)}
            />
            {producer && <CrewLog channel={channel} fixtureOf={fixtureOf} />}
            <div className="grid min-w-0 gap-3 lg:grid-cols-2 lg:items-start">
              <TableMoves swings={table?.swings ?? []} />
              <EarlierCuts history={channel.history} fixtureOf={fixtureOf} />
            </div>
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
          {/* The rail: why we're here, then the fan's XI, the table, and the Golden Boot. */}
          <aside className="grid min-w-0 gap-3">
            <StoryCard
              channel={channel}
              fixtureOf={fixtureOf}
              forWhom={forWhom}
              className="hidden xl:block"
            />
            {channel.lens.kind === "fantasy" && (
              <FantasyXi
                lens={channel.lens}
                clubs={clubs}
                onAirMatchId={channel.on_air.match_id}
                onEdit={() => setPicking(true)}
              />
            )}
            {table && (
              <LeagueTable
                table={table}
                cards={byId}
                onAirMatchId={channel.on_air.match_id}
                clubId={channel.lens.club_id ?? null}
              />
            )}
            {table && (
              <GoldenBoot
                boot={table.golden_boot}
                onAirClubIds={onAirClubs(byId.get(channel.on_air.match_id))}
              />
            )}
          </aside>
        </main>
        {picker}
      </div>
    </MotionConfig>
  );
}

function onAirClubs(card: MatchCard | undefined): ReadonlySet<string> {
  return new Set(card ? [card.home.club_id, card.away.club_id] : []);
}

/** On a fan's own whip-around, which matches are theirs, and why. */
function tagsFor(
  channel: Channel,
  signals: MatchSignal[],
): Map<string, string> | undefined {
  const { lens } = channel;
  if (lens.kind === "fantasy") {
    const counts = new Map<string, number>();
    for (const p of lens.xi)
      counts.set(p.match_id, (counts.get(p.match_id) ?? 0) + 1);
    return new Map(
      [...counts].map(([matchId, n]) => [matchId, `${n} of your XI`]),
    );
  }
  if (lens.kind === "club") {
    const tags = new Map<string, string>();
    for (const s of signals) {
      if ([s.home.club_id, s.away.club_id].includes(lens.club_id ?? ""))
        tags.set(s.match_id, "Your match");
      else if (s.home.stake_summary || s.away.stake_summary)
        tags.set(s.match_id, "Matters to you");
    }
    return tags;
  }
  return undefined;
}
