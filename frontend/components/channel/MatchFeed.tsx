"use client";

import { AnimatePresence } from "motion/react";

import { LiveCamera } from "@/components/broadcast/LiveCamera";
import { LowerThird } from "@/components/broadcast/LowerThird";
import { Scorebug } from "@/components/broadcast/Scorebug";
import { cameraAim } from "@/components/control-room/ProgramMonitor";
import { onAirGraphic, scoreAt } from "@/lib/controlRoom";
import { formatClock } from "@/lib/format";
import { type Audience, type Lang, forFeed } from "@/lib/i18n";
import { usePlaybackClock } from "@/lib/live/usePlaybackClock";
import { type LiveMatch, useLiveMatch } from "@/lib/live/useLiveMatch";
import { MatchContext, type MatchInfo } from "@/lib/match";
import { useMatchFrame } from "@/lib/useMatchFrame";

export type FeedView = { audience: Audience; lang: Lang };

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
}: {
  matchId: string;
  fixture: string;
  view: FeedView;
  /** False while the cut package is on screen, so two lower thirds never overlap. */
  graphics: boolean;
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
}: {
  live: LiveMatch;
  info: MatchInfo;
  baseline: NonNullable<LiveMatch["baseline"]>;
  fixture: string;
  view: FeedView;
  graphics: boolean;
}) {
  const frame = useMatchFrame(live.source);
  const clockMs = usePlaybackClock(live.source.getClockMs);
  const score = scoreAt(info, baseline, live.events, clockMs);
  const onAir = graphics ? onAirGraphic(live.desk) : null;
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
      {frame ? (
        <LiveCamera
          frame={frame}
          aimX={cameraAim(live.source, frame)}
          tag={tag}
          focusPlayerId={null}
        />
      ) : (
        <Placeholder fixture={fixture} />
      )}
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
