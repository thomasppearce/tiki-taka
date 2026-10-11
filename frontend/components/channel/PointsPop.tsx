"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

import type { FantasyPlayer, Lens } from "@/lib/contracts.generated";
import { DURATION, EASE } from "@/lib/motion";

const POP_MS = 7_000;
// The moments worth interrupting the picture for; playing time and clean sheets just add up.
const BIG = ["Goal", "Assist", "Red card"];

type Pop = { id: string; name: string; label: string; points: number };

/**
 * On a fan's fantasy whip-around, their XI's big moments pop into the corner of the picture as
 * the points land, wherever in the league they happen ("+4 DESAI GOAL").
 */
export function PointsPop({ lens }: { lens: Lens }) {
  const [seen, setSeen] = useState<FantasyPlayer[] | null>(null);
  const [pops, setPops] = useState<Pop[]>([]);

  // Compare with the last points we saw (derived during render, React's pattern for state
  // that follows a prop). The first snapshot is the baseline: nothing pops on arrival.
  if (seen !== lens.xi) {
    setSeen(lens.xi);
    if (seen) {
      const before = new Map(seen.map((p) => [p.player_id, p]));
      const fresh = lens.xi.flatMap((p) =>
        BIG.flatMap((label) => {
          const was = count(before.get(p.player_id), label);
          const now = count(p, label);
          const item = p.items.findLast((i) => i.label === label);
          return now > was && item
            ? [
                {
                  id: `${p.player_id}-${label}-${now}`,
                  name: p.name.split(" ").slice(1).join(" ") || p.name,
                  label,
                  points: item.points,
                },
              ]
            : [];
        }),
      );
      if (fresh.length) setPops((current) => [...current, ...fresh]);
    }
  }

  useEffect(() => {
    if (!pops.length) return;
    const timer = setTimeout(
      () => setPops((current) => current.slice(1)),
      POP_MS,
    );
    return () => clearTimeout(timer);
  }, [pops]);

  return (
    <div className="absolute top-[9.5cqw] right-[3.5cqw] flex flex-col items-end gap-[0.8cqw]">
      <AnimatePresence>
        {pops.slice(0, 3).map((pop) => (
          <motion.p
            key={pop.id}
            className="flex h-[4.4cqw] items-stretch font-broadcast text-[2.2cqw] leading-none font-semibold text-ink uppercase"
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, transition: { duration: DURATION.medium } }}
            transition={{ duration: DURATION.slow, ease: EASE.smoothOut }}
          >
            <span
              className={`flex items-center px-[1.2cqw] tabular-nums ${
                pop.points > 0
                  ? "bg-air text-ink-on-fill"
                  : "bg-raised text-ink-2"
              }`}
            >
              {pop.points > 0 ? `+${pop.points}` : pop.points}
            </span>
            <span className="flex items-center bg-page/95 px-[1.2cqw] tracking-wide">
              {pop.name}
              <span className="ml-[1cqw] text-ink-3">{pop.label}</span>
            </span>
          </motion.p>
        ))}
      </AnimatePresence>
    </div>
  );
}

function count(player: FantasyPlayer | undefined, label: string): number {
  return player?.items.filter((i) => i.label === label).length ?? 0;
}
