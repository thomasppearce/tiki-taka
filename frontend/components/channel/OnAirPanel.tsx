"use client";

import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CutBanner, Stinger } from "@/components/channel/CutBanner";
import { type FeedView, MatchFeed } from "@/components/channel/MatchFeed";
import { PointsPop } from "@/components/channel/PointsPop";
import { Ticker, type TickerItem } from "@/components/channel/Ticker";
import { Panel } from "@/components/ui/Panel";
import type { Cut, Lens, PendingCut } from "@/lib/contracts.generated";
import { useCountdown } from "@/lib/live/useCountdown";
import { DURATION, EASE } from "@/lib/motion";

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
  // A goal on the match already on air brings the package back, as a goal: it changed it.
  const [goal, setGoal] = useState<{ cutId: string; eventId: string } | null>(
    null,
  );
  const goalOnAir = goal?.cutId === cut.cut_id ? goal.eventId : null;
  const bannerKey = goalOnAir ? `${cut.cut_id}:${goalOnAir}` : cut.cut_id;
  const [bannerDone, setBannerDone] = useState<string | null>(null);
  const [replaying, setReplaying] = useState(false);
  const [replayedFor, setReplayedFor] = useState<string | null>(null);
  const [firstCut] = useState(cut.cut_id);
  const onReplay = useCallback(
    (active: boolean) => {
      setReplaying(active);
      if (active) setReplayedFor(bannerKey);
    },
    [bannerKey],
  );
  const onGoal = useCallback(
    (eventId: string) => setGoal({ cutId: cut.cut_id, eventId }),
    [cut.cut_id],
  );
  useEffect(() => {
    if (replaying) return;
    const after =
      replayedFor === bannerKey ? BANNER_AFTER_REPLAY_MS : BANNER_MS;
    const timer = setTimeout(() => setBannerDone(bannerKey), after);
    return () => clearTimeout(timer);
  }, [bannerKey, replaying, replayedFor]);
  const banner = bannerDone !== bannerKey;

  const fixture = fixtureOf(cut.match_id);
  const ringed = useMemo(
    () =>
      lens?.kind === "fantasy"
        ? new Set(lens.xi.map((p) => p.player_id))
        : undefined,
    [lens],
  );
  const ticker = tickerItems(cut, forWhom);
  const split = cut.also_match_id ?? null;
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
        <div
          className={`@container relative isolate aspect-video overflow-hidden rounded-md bg-page ${
            // In a split the banner drops below the boxes, clear of the second box's caption.
            split
              ? "[--lower-third-bottom:2cqw]"
              : "[--lower-third-bottom:8cqw]"
          }`}
        >
          {/* The match on air fills the picture; in a split it moves into the left box, so
              its feed (and any replay) carries on without a restart. */}
          <motion.div
            layout
            transition={{ duration: DURATION.verySlow, ease: EASE.smoothOut }}
            className={
              split
                ? `@container absolute ${BOX} left-[1.75cqw] overflow-hidden rounded-[0.5cqw]`
                : "@container absolute inset-0 overflow-hidden"
            }
          >
            <MatchFeed
              key={cut.match_id}
              matchId={cut.match_id}
              fixture={fixture}
              view={view}
              graphics={!banner}
              replayEventId={
                cut.cut_id === firstCut ? null : cut.replay_event_id
              }
              onReplay={onReplay}
              onGoal={onGoal}
              ringed={ringed}
            />
          </motion.div>
          <AnimatePresence>
            {split && (
              <SplitBox
                key={split}
                matchId={split}
                fixture={fixture}
                alsoFixture={fixtureOf(split)}
                why={cut.also_why ?? null}
                view={view}
                ringed={ringed}
              />
            )}
          </AnimatePresence>
          {!banner && <Ticker key={cut.cut_id} items={ticker} />}
          {cut.cut_id !== firstCut && <Stinger cutId={cut.cut_id} />}
          <AnimatePresence>
            {banner && (
              <CutBanner
                key={bannerKey}
                cut={cut}
                fixture={fixture}
                forWhom={forWhom}
                goal={goalOnAir !== null}
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

/** Each box of a split: half the picture's width, 16:9, below the labels. */
const BOX = "top-[5.5cqw] aspect-video w-[47.5cqw]";
const noReplay = () => undefined;

/**
 * The double box: the match the goal cut left stays live beside it while it still
 * matters, with a label over each box and why the second one is still on screen.
 */
function SplitBox({
  matchId,
  fixture,
  alsoFixture,
  why,
  view,
  ringed,
}: {
  matchId: string;
  fixture: string;
  alsoFixture: string;
  why: string | null;
  view: FeedView;
  ringed?: ReadonlySet<string>;
}) {
  const label =
    "absolute top-[1.6cqw] w-[47.5cqw] truncate font-broadcast text-[1.7cqw] leading-none font-semibold tracking-wider uppercase";
  return (
    <motion.div
      className="absolute inset-0"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: DURATION.slow, ease: EASE.smoothOut }}
    >
      <p className={`${label} left-[1.75cqw] text-ink`}>{fixture}</p>
      <p className={`${label} right-[1.75cqw] text-ink-2`}>
        <span className="mr-[0.8cqw] bg-raised px-[0.6cqw] py-[0.2cqw] text-ink">
          Still on
        </span>
        {alsoFixture}
      </p>
      <motion.div
        className={`@container absolute ${BOX} right-[1.75cqw] overflow-hidden rounded-[0.5cqw]`}
        initial={{ x: "12%" }}
        animate={{ x: 0 }}
        transition={{ duration: DURATION.verySlow, ease: EASE.smoothOut }}
      >
        <MatchFeed
          matchId={matchId}
          fixture={alsoFixture}
          view={view}
          graphics={false}
          replayEventId={null}
          onReplay={noReplay}
          ringed={ringed}
        />
        {why && (
          <p className="absolute inset-x-0 bottom-0 bg-page/90 px-[2.4cqw] py-[1.6cqw] font-broadcast text-[3.2cqw] leading-tight font-semibold text-ink">
            {why}
          </p>
        )}
      </motion.div>
    </motion.div>
  );
}

/** What the ticker says, in turn: for you first (on a fan's own whip-around), then why, a
 * player's story, and what's at stake. */
function tickerItems(cut: Cut, forWhom: string | null): TickerItem[] {
  const { why, at_stake: atStake, for_you: forYou, storyline } = cut.package;
  return [
    ...(forWhom && forYou
      ? [{ label: `For ${forWhom}`, text: forYou, accent: true }]
      : []),
    { label: "Why we're here", text: why },
    ...(storyline ? [{ label: "Storyline", text: storyline }] : []),
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
