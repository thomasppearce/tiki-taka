"use client";

import { AnimatePresence } from "motion/react";

import { LowerThird } from "@/components/broadcast/LowerThird";
import { PlayerTag } from "@/components/broadcast/PlayerTag";
import { Scorebug } from "@/components/broadcast/Scorebug";
import { SyntheticFeed } from "@/components/broadcast/SyntheticFeed";
import { Panel } from "@/components/ui/Panel";
import { FEEDS, type FeedId, type OnAirGraphic } from "@/lib/controlRoom";
import { forFeed } from "@/lib/i18n";
import { MATCH } from "@/lib/mock";

/** The program output: synthetic camera feed plus whatever graphic is on air for this feed. */
export function ProgramMonitor({
  clock,
  feed,
  onAir,
  className,
}: {
  clock: string;
  feed: FeedId;
  onAir: OnAirGraphic | null;
  className?: string;
}) {
  const { audience, lang, label } = FEEDS[feed];

  return (
    <Panel
      title="Program"
      aside={<Tally feedLabel={label} live={onAir !== null} />}
      className={className}
    >
      <div className="p-3">
        <div className="@container relative isolate aspect-video overflow-hidden rounded-md bg-page">
          <SyntheticFeed />
          <Scorebug score={MATCH.score} clock={clock} />
          <AnimatePresence mode="wait">
            {onAir?.template === "player_tag" && onAir.playerId ? (
              <PlayerTag
                key={onAir.id}
                playerId={onAir.playerId}
                line={forFeed(onAir.headline, audience, lang)}
              />
            ) : onAir ? (
              <LowerThird
                key={onAir.id}
                label={onAir.label[lang]}
                headline={forFeed(onAir.headline, audience, lang)}
                split={onAir.split}
                splitLabel={onAir.splitLabel?.[lang]}
              />
            ) : null}
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
