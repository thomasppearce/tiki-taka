"use client";

import { AnimatePresence } from "motion/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CutBanner, Stinger } from "@/components/channel/CutBanner";
import { type FeedView, MatchFeed } from "@/components/channel/MatchFeed";
import { PointsPop } from "@/components/channel/PointsPop";
import { Ticker, type TickerItem } from "@/components/channel/Ticker";
import { Panel } from "@/components/ui/Panel";
import type { Cut, Lens, PendingCut } from "@/lib/contracts.generated";
import { useCountdown } from "@/lib/live/useCountdown";

const BANNER_MS = 9_000;
const BANNER_AFTER_REPLAY_MS = 5_000;

/**
 * The channel's program output: the match on air, the stinger on every cut, the cut package as a
 * lower third for a few seconds, then the ticker that keeps why we're here (and what's at stake,
 * and on a fan's own whip-around what it means for them) on the picture, and the Director's next
 * cut counting down in the corner. On a fantasy whip-around the fan's XI is ringed on the pitch
 * and their points pop in as they land.
 */
export function OnAirPanel({
  cut,
  pending,
  fixtureOf,
  serverClockMs,
  view,
  title = "On air",
  forWhom = null,
  lens = null,
}: {
  cut: Cut;
  pending: PendingCut | null;
  fixtureOf: (matchId: string) => string;
  serverClockMs: () => number;
  view: FeedView;
  title?: string;
  /** On a fan's own whip-around: whose ("Westmere Athletic", "your XI"). */
  forWhom?: string | null;
  lens?: Lens | null;
}) {
  // The package shows for a few seconds after each cut, and through the replay a cut opens
  // with. The page's first cut gets no stinger and no replay: it was already on air.
  const [bannerDone, setBannerDone] = useState<string | null>(null);
  const [replaying, setReplaying] = useState(false);
  const [replayedFor, setReplayedFor] = useState<string | null>(null);
  const [firstCut] = useState(cut.cut_id);
  const onReplay = useCallback(
    (active: boolean) => {
      setReplaying(active);
      if (active) setReplayedFor(cut.cut_id);
    },
    [cut.cut_id],
  );
  useEffect(() => {
    if (replaying) return;
    const after =
      replayedFor === cut.cut_id ? BANNER_AFTER_REPLAY_MS : BANNER_MS;
    const timer = setTimeout(() => setBannerDone(cut.cut_id), after);
    return () => clearTimeout(timer);
  }, [cut.cut_id, replaying, replayedFor]);
  const banner = bannerDone !== cut.cut_id;

  const fixture = fixtureOf(cut.match_id);
  const ringed = useMemo(
    () =>
      lens?.kind === "fantasy"
        ? new Set(lens.xi.map((p) => p.player_id))
        : undefined,
    [lens],
  );
  const ticker = tickerItems(cut, forWhom);
  return (
    <Panel
      title={title}
      aside={
        <p className="flex items-center gap-2 text-xs text-ink-2">
          <span className="rounded-md bg-air px-1.5 py-0.5 font-medium text-ink-on-fill">
            Live
          </span>
          <span className="truncate">{fixture}</span>
        </p>
      }
    >
      <div className="p-3">
        <div className="@container relative isolate aspect-video overflow-hidden rounded-md bg-page [--lower-third-bottom:8cqw]">
          <MatchFeed
            key={cut.match_id}
            matchId={cut.match_id}
            fixture={fixture}
            view={view}
            graphics={!banner}
            replayEventId={cut.cut_id === firstCut ? null : cut.replay_event_id}
            onReplay={onReplay}
            ringed={ringed}
          />
          {!banner && <Ticker key={cut.cut_id} items={ticker} />}
          {cut.cut_id !== firstCut && <Stinger cutId={cut.cut_id} />}
          <AnimatePresence>
            {banner && (
              <CutBanner
                key={cut.cut_id}
                cut={cut}
                fixture={fixture}
                forWhom={forWhom}
              />
            )}
          </AnimatePresence>
          {lens?.kind === "fantasy" && <PointsPop lens={lens} />}
          {pending && (
            <NextUp
              pending={pending}
              fixture={fixtureOf(pending.match_id)}
              serverClockMs={serverClockMs}
            />
          )}
        </div>
      </div>
    </Panel>
  );
}

/** What the ticker says, in turn: for you first (on a fan's own whip-around), then why, then
 * what's at stake. */
function tickerItems(cut: Cut, forWhom: string | null): TickerItem[] {
  const { why, at_stake: atStake, for_you: forYou } = cut.package;
  return [
    ...(forWhom && forYou
      ? [{ label: `For ${forWhom}`, text: forYou, accent: true }]
      : []),
    { label: "Why we're here", text: why },
    ...(atStake ? [{ label: "At stake", text: atStake }] : []),
  ];
}

/** The Director's next cut, top right of the picture, like a gallery's preview tally. */
function NextUp({
  pending,
  fixture,
  serverClockMs,
}: {
  pending: PendingCut;
  fixture: string;
  serverClockMs: () => number;
}) {
  const seconds = useCountdown(pending.take_at_ms, serverClockMs);
  return (
    <div className="absolute top-[3.5cqw] right-[3.5cqw] flex h-[4.4cqw] items-stretch font-broadcast text-[2.4cqw] leading-none font-semibold text-ink uppercase">
      <span className="flex items-center bg-air px-[1.3cqw] tracking-wider text-ink-on-fill">
        Next
      </span>
      <span className="flex items-center bg-page/95 px-[1.3cqw] tracking-wide">
        {fixture}
      </span>
      <span className="flex w-[4.4cqw] items-center justify-center bg-raised/95 tabular-nums">
        {seconds}
      </span>
    </div>
  );
}
