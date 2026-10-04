"use client";

import { AnimatePresence } from "motion/react";

import { LiveCamera } from "@/components/broadcast/LiveCamera";
import { LowerThird } from "@/components/broadcast/LowerThird";
import { Scorebug } from "@/components/broadcast/Scorebug";
import { Panel } from "@/components/ui/Panel";
import { FEEDS, type FeedId, type OnAirGraphic } from "@/lib/controlRoom";
import { forFeed } from "@/lib/i18n";
import { MATCH } from "@/lib/mock";
import { useMatchFrame } from "@/lib/useMatchFrame";

/**
 * The program output: the live camera on the synthetic match plus whatever graphic is on air for
 * this feed. Reads the same tracking frame as the tactical view, so both show the same instant.
 */
export function ProgramMonitor({
  clock,
  getClockMs,
  feed,
  onAir,
  className,
}: {
  clock: string;
  getClockMs: () => number;
  feed: FeedId;
  onAir: OnAirGraphic | null;
  className?: string;
}) {
  const { audience, lang, label } = FEEDS[feed];
  const frame = useMatchFrame(getClockMs);
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
          <LiveCamera frame={frame} tag={tag} />
          <Scorebug score={MATCH.score} clock={clock} />
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
