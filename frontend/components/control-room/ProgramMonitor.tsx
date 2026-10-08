"use client";

import { AnimatePresence } from "motion/react";

import { LiveCamera } from "@/components/broadcast/LiveCamera";
import { LowerThird } from "@/components/broadcast/LowerThird";
import { Scorebug } from "@/components/broadcast/Scorebug";
import { Panel } from "@/components/ui/Panel";
import type { TrackingFrame } from "@/lib/contracts.generated";
import type { OnAirGraphic } from "@/lib/controlRoom";
import { type Audience, type Lang, forFeed } from "@/lib/i18n";
import type { FrameSource } from "@/lib/live/useLiveMatch";
import type { Side } from "@/lib/match";
import { useMatchFrame } from "@/lib/useMatchFrame";

const CAMERA_LOOKBACK_MS = 2_000;
const CAMERA_SAMPLES = 10;

/**
 * The program output: the live camera on the synthetic match plus whatever graphic is on air for
 * this feed. Reads the same tracking frames as the tactical view, so both show the same instant.
 */
export function ProgramMonitor({
  clock,
  source,
  score,
  view,
  onAir,
  focusPlayerId = null,
  className,
}: {
  clock: string;
  source: FrameSource;
  score: Record<Side, number>;
  /** Whose feed this is: the graphics are written for this audience and language. */
  view: { audience: Audience; lang: Lang; label: string };
  onAir: OnAirGraphic | null;
  focusPlayerId?: string | null;
  className?: string;
}) {
  const { audience, lang, label } = view;
  const frame = useMatchFrame(source);
  const tag =
    onAir?.template === "player_tag" && onAir.playerId
      ? {
          id: onAir.id,
          playerId: onAir.playerId,
          line: forFeed(onAir.headline, audience, lang),
        }
      : null;

  return (
    <Panel
      title="Program"
      aside={<Tally feedLabel={label} live={onAir !== null} />}
      className={className}
    >
      <div className="p-3">
        <div className="@container relative isolate aspect-video overflow-hidden rounded-md bg-page">
          {frame ? (
            <LiveCamera
              frame={frame}
              aimX={cameraAim(source, frame)}
              tag={tag}
              focusPlayerId={focusPlayerId}
            />
          ) : (
            <p className="absolute inset-0 grid place-items-center text-sm text-ink-3">
              Waiting for the first frame
            </p>
          )}
          <Scorebug score={score} clock={clock} />
          <AnimatePresence>
            {onAir?.template === "lower_third" && (
              <LowerThird
                key={onAir.id}
                label={onAir.label[lang]}
                headline={forFeed(onAir.headline, audience, lang)}
                split={onAir.split}
                splitLabel={onAir.splitLabel?.[lang]}
              />
            )}
          </AnimatePresence>
        </div>
      </div>
    </Panel>
  );
}

/**
 * Where the camera aims: the ball's average x over the last two seconds, so it follows play
 * smoothly instead of snapping to every pass.
 */
export function cameraAim(source: FrameSource, frame: TrackingFrame): number {
  let sum = 0;
  let count = 0;
  for (let k = 0; k < CAMERA_SAMPLES; k++) {
    const x = source.ballXAt(
      frame.match_clock_ms - (k * CAMERA_LOOKBACK_MS) / CAMERA_SAMPLES,
    );
    if (x !== null) {
      sum += x;
      count += 1;
    }
  }
  return count ? sum / count : frame.ball.x;
}

function Tally({ feedLabel, live }: { feedLabel: string; live: boolean }) {
  return (
    <p className="flex items-center gap-2 text-xs text-ink-2">
      <span className="text-ink-3">{feedLabel} feed</span>
      <span
        className={`rounded-md px-1.5 py-0.5 font-medium transition-[background-color,color] duration-(--duration-fast) ease-(--ease-smooth-out) ${
          live ? "bg-air text-ink-on-fill" : "bg-raised text-ink-3"
        }`}
      >
        {live ? "Graphic on air" : "Clean feed"}
      </span>
    </p>
  );
}
