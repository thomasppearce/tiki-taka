"use client";

import { MotionConfig } from "motion/react";
import { useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import { OnAirPanel } from "@/components/channel/OnAirPanel";
import { StoryCard } from "@/components/channel/StoryCard";
import { Crest } from "@/components/Crest";
import { SiteHeader } from "@/components/SiteHeader";
import type { ClubRef } from "@/lib/contracts.generated";
import { useChannel } from "@/lib/live/useChannel";
import { useMatchday } from "@/lib/live/useMatchday";
import { GUEST_PREFS } from "@/lib/role";

// The demo's pair: the two clubs Desai's 93rd-minute goal swaps in and out of the drop.
const DEFAULT_A = "t_wma";
const DEFAULT_B = "t_crb";

/**
 * Two fans' whip-arounds side by side, on the same clock: the same goal, cut to and told for
 * each of them. The clubs come from the URL (?a=t_wma&b=t_crb); any two clubs work.
 */
export function SplitPage() {
  const params = useSearchParams();
  const a = params.get("a") ?? DEFAULT_A;
  const b = params.get("b") ?? DEFAULT_B;
  const { matchday } = useMatchday();
  const cards = useMemo(
    () => matchday?.leagues.flatMap((l) => l.matches) ?? [],
    [matchday],
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
      const card = cards.find((c) => c.match_id === matchId);
      return card ? `${card.home.name} v ${card.away.name}` : "";
    },
    [cards],
  );
  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-dvh flex-col bg-page">
        <SiteHeader>
          <p className="text-sm whitespace-nowrap text-ink">
            Two fans, two channels
          </p>
        </SiteHeader>
        <main className="grid flex-1 grid-cols-1 gap-3 p-3 lg:grid-cols-2 lg:items-start">
          {[a, b].map((clubId) => (
            <FanSide
              key={clubId}
              club={clubs.get(clubId) ?? null}
              clubId={clubId}
              fixtureOf={fixtureOf}
            />
          ))}
        </main>
      </div>
    </MotionConfig>
  );
}

function FanSide({
  club,
  clubId,
  fixtureOf,
}: {
  club: ClubRef | null;
  clubId: string;
  fixtureOf: (matchId: string) => string;
}) {
  const live = useChannel(`club:${clubId}`);
  const { channel } = live;
  const name = club?.name ?? clubId;
  return (
    <section
      aria-label={`${name} fan's channel`}
      className="grid min-w-0 gap-3"
    >
      <h2 className="flex items-center gap-2 text-sm text-ink-2">
        {club && <Crest club={club} size={20} />}
        <span>
          A <span className="font-medium text-ink">{name}</span> fan&rsquo;s
          channel
        </span>
        {channel && (
          <span className="ml-auto font-mono text-ink-3 tabular-nums">
            {`${Math.floor(channel.clock_ms / 60_000) + 1}'`}
          </span>
        )}
      </h2>
      {channel ? (
        <>
          <OnAirPanel
            cut={channel.on_air}
            pending={
              channel.held || channel.pinned_match_id ? null : channel.pending
            }
            fixtureOf={fixtureOf}
            serverClockMs={live.serverClockMs}
            view={GUEST_PREFS}
            title={`${name}'s whip-around`}
            forWhom={name}
            lens={channel.lens}
          />
          <StoryCard channel={channel} fixtureOf={fixtureOf} forWhom={name} />
        </>
      ) : (
        <p className="rounded-lg border border-line bg-panel px-4 py-3 text-sm text-ink-3">
          Tuning in to {name}&rsquo;s channel
        </p>
      )}
    </section>
  );
}
