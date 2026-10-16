"use client";

import { AnimatePresence } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";

import { LiveCamera } from "@/components/broadcast/LiveCamera";
import { LowerThird } from "@/components/broadcast/LowerThird";
import { Scorebug } from "@/components/broadcast/Scorebug";
import { Stinger } from "@/components/channel/CutBanner";
import { ReplayPlayer } from "@/components/channel/ReplayPlayer";
import { cameraAim } from "@/components/control-room/ProgramMonitor";
import { getJson } from "@/lib/api";
import type { Replay } from "@/lib/contracts.generated";
import { onAirGraphic, scoreAt } from "@/lib/controlRoom";
import { formatClock } from "@/lib/format";
import { type Audience, type Lang, forFeed } from "@/lib/i18n";
import { usePlaybackClock } from "@/lib/live/usePlaybackClock";
import { type LiveMatch, useLiveMatch } from "@/lib/live/useLiveMatch";
import { MatchContext, type MatchInfo } from "@/lib/match";
import { useMatchFrame } from "@/lib/useMatchFrame";

export type FeedView = { audience: Audience; lang: Lang };

/** A goal on air gets its action replay this long after it goes in: the celebration first,
 * then the match's goal graphic (a few seconds after the goal) gets its moment on screen. */
const ON_AIR_REPLAY_DELAY_MS = 9_000;

/**
 * One match's picture inside the channel's monitor: the live camera, the scorebug, and the
 * match's own approved graphics. Mounted per match (keyed by match id), so a cut starts a fresh
 * stream and frame buffer: all ten matches share one clock, so frames from two matches must never
 * mix in one buffer.
 */
export function MatchFeed({
  matchId,
  fixture,
  view,
  graphics,
  replayEventId,
  onReplay,
  ringed,
}: {
  matchId: string;
  fixture: string;
  view: FeedView;
  /** Players to ring on the pitch (a fan's fantasy XI). */
  ringed?: ReadonlySet<string>;
  /** False while the cut package is on screen, so two lower thirds never overlap. */
  graphics: boolean;
  /** Open with a replay of this goal or chance (the cut's), before going live. */
  replayEventId: string | null;
  /** Told when a replay starts and ends, so the cut banner can stay up through it. */
  onReplay: (active: boolean) => void;
}) {
  const live = useLiveMatch(matchId);
  if (!live.info || !live.baseline) return <Placeholder fixture={fixture} />;
  return (
    <MatchContext value={live.info}>
      <Picture
        live={live}
        info={live.info}
        baseline={live.baseline}
        fixture={fixture}
        view={view}
        graphics={graphics}
        replayEventId={replayEventId}
        onReplay={onReplay}
        ringed={ringed}
      />
    </MatchContext>
  );
}

function Picture({
  live,
  info,
  baseline,
  fixture,
  view,
  graphics,
  replayEventId,
  onReplay,
  ringed,
}: {
  live: LiveMatch;
  info: MatchInfo;
  baseline: NonNullable<LiveMatch["baseline"]>;
  fixture: string;
  view: FeedView;
  graphics: boolean;
  replayEventId: string | null;
  onReplay: (active: boolean) => void;
  ringed?: ReadonlySet<string>;
}) {
  const frame = useMatchFrame(live.source);
  const clockMs = usePlaybackClock(live.source.getClockMs);
  const score = scoreAt(info, baseline, live.events, clockMs);
  const replays = useReplays(
    info.matchId,
    replayEventId,
    live,
    clockMs,
    onReplay,
  );
  const replay = replays.current;
  const onAir =
    graphics && !replay ? onAirGraphic(live.desk, live.events) : null;
  const tag =
    onAir?.template === "player_tag" && onAir.playerId
      ? {
          id: onAir.id,
          playerId: onAir.playerId,
          line: forFeed(onAir.headline, view.audience, view.lang),
        }
      : null;
  return (
    <>
      {replay ? (
        <ReplayPlayer
          replay={replay.data}
          showLabel={!replay.fromCut}
          onDone={replays.end}
        />
      ) : frame && !replays.waiting ? (
        <LiveCamera
          frame={frame}
          aimX={cameraAim(live.source, frame)}
          tag={tag}
          focusPlayerId={null}
          ringed={ringed}
        />
      ) : (
        <Placeholder fixture={fixture} />
      )}
      {replays.ended && <Stinger cutId={replays.ended} />}
      <Scorebug score={score} clock={formatClock(clockMs)} />
      <AnimatePresence>
        {onAir?.template === "lower_third" && (
          <LowerThird
            key={onAir.id}
            label={onAir.label[view.lang]}
            headline={forFeed(onAir.headline, view.audience, view.lang)}
          />
        )}
      </AnimatePresence>
    </>
  );
}

type Playing = { data: Replay; fromCut: boolean };

/**
 * The replays this feed plays: the cut's (if it opened with one), then an action replay of any
 * goal that goes in while the match is on air, a few seconds after it. Each plays once; a failed
 * fetch just skips it.
 */
function useReplays(
  matchId: string,
  cutReplayId: string | null,
  live: LiveMatch,
  clockMs: number,
  onReplay: (active: boolean) => void,
) {
  const [current, setCurrent] = useState<Playing | null>(null);
  const [waiting, setWaiting] = useState(cutReplayId !== null);
  const [ended, setEnded] = useState<string | null>(null);
  const played = useRef(new Set<string>());
  const mountedAt = useRef<number | null>(null);

  const play = useCallback(
    (eventId: string, fromCut: boolean) => {
      played.current.add(eventId);
      getJson<Replay>(`/api/matches/${matchId}/replays/${eventId}`)
        .then((data) => {
          setCurrent({ data, fromCut });
          onReplay(true);
        })
        .catch(() => undefined)
        .finally(() => setWaiting(false));
    },
    [matchId, onReplay],
  );

  // The cut's replay, once, as the feed opens.
  useEffect(() => {
    if (cutReplayId && !played.current.has(cutReplayId))
      play(cutReplayId, true);
  }, [cutReplayId, play]);

  // Goals on air: replay each one a few seconds after it goes in.
  useEffect(() => {
    mountedAt.current ??= clockMs;
    if (current || waiting) return;
    const goal = live.events.find(
      (e) =>
        e.type === "goal" &&
        e.match_clock_ms > (mountedAt.current ?? 0) &&
        !played.current.has(e.event_id) &&
        clockMs >= e.match_clock_ms + ON_AIR_REPLAY_DELAY_MS,
    );
    if (goal) play(goal.event_id, false);
  }, [live.events, clockMs, current, waiting, play]);

  const end = useCallback(() => {
    setCurrent((playing) => {
      if (playing) setEnded(`end_${playing.data.event_id}`);
      return null;
    });
    onReplay(false);
  }, [onReplay]);

  return { current, waiting, ended, end };
}

/** While the new match's first frames arrive (under a second, behind the stinger). */
function Placeholder({ fixture }: { fixture: string }) {
  return (
    <div className="absolute inset-0 grid place-items-center bg-pitch">
      <p className="font-broadcast text-[3cqw] font-semibold tracking-wider text-ink-3 uppercase">
        {fixture}
      </p>
    </div>
  );
}
