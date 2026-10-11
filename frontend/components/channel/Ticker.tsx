"use client";

import { motion } from "motion/react";
import { useEffect, useState } from "react";

import { SwapText } from "@/components/ui/SwapText";
import { DURATION, EASE } from "@/lib/motion";

const TICKER_MS = 7_000;

export type TickerItem = { label: string; text: string; accent?: boolean };

/**
 * The channel's bottom bar: why we're here, what's at stake, and on a fan's own whip-around what
 * it means for them, taking turns so the explanation stays on the picture once the cut's banner
 * clears. Lower thirds sit above it (the feed sets --lower-third-bottom).
 */
export function Ticker({ items }: { items: TickerItem[] }) {
  const [turn, setTurn] = useState(0);
  useEffect(() => {
    if (items.length < 2) return;
    const timer = setInterval(() => setTurn((n) => n + 1), TICKER_MS);
    return () => clearInterval(timer);
  }, [items.length]);
  if (!items.length) return null;
  const item = items[turn % items.length];
  return (
    <motion.div
      className="absolute inset-x-0 bottom-0 flex h-[6cqw] items-stretch font-broadcast leading-[1.1]"
      initial={{ opacity: 0, y: "100%" }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATION.slow, ease: EASE.smoothOut }}
    >
      <div
        className={`flex w-[17cqw] shrink-0 items-center px-[1.6cqw] text-[1.6cqw] font-semibold tracking-wider uppercase transition-[background-color,color] duration-(--duration-fast) ease-(--ease-out) ${
          item.accent ? "bg-air text-ink-on-fill" : "bg-raised text-ink-2"
        }`}
      >
        <SwapText text={item.label} className="line-clamp-2" />
      </div>
      <div className="flex min-w-0 flex-1 items-center bg-page/90 px-[1.8cqw] text-[2cqw] font-semibold text-ink">
        <SwapText text={item.text} as="p" className="line-clamp-2" />
      </div>
    </motion.div>
  );
}
