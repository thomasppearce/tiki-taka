"use client";

import { motion } from "motion/react";
import { useState } from "react";

import type { Cut } from "@/lib/contracts.generated";
import { DURATION, EASE } from "@/lib/motion";

const LABEL: Record<Cut["reason"], string> = {
  goal: "Goal",
  pressure: "Why we're here",
  check_in: "Meanwhile",
  manual: "Producer's call",
  kickoff: "Live",
};

/**
 * The cut package on air: why we cut here, what it means for this fan (on their own
 * whip-around), and what's at stake. Same plate as the lower third (the air spine, condensed
 * caps), wiping in as the stinger clears.
 */
export function CutBanner({
  cut,
  fixture,
  forWhom = null,
}: {
  cut: Cut;
  fixture: string;
  forWhom?: string | null;
}) {
  const { why, at_stake: atStake, for_you: forYou } = cut.package;
  return (
    <motion.div
      className="absolute bottom-[var(--lower-third-bottom,4.5cqw)] left-[3.5cqw] w-max max-w-[88cqw] min-w-[52cqw] font-broadcast text-ink"
      initial={{ clipPath: "inset(0 100% 0 0)" }}
      animate={{ clipPath: "inset(0 0% 0 0)" }}
      exit={{
        opacity: 0,
        transition: { duration: DURATION.medium, ease: EASE.inOut },
      }}
      transition={{
        duration: DURATION.verySlow,
        ease: EASE.smoothOut,
        delay: STINGER_S,
      }}
    >
      <div className="flex">
        <div className="w-[0.7cqw] shrink-0 bg-air" />
        <div className="flex-1 bg-page/95 px-[2.2cqw] pt-[1.5cqw] pb-[1.6cqw]">
          <p className="text-[1.9cqw] leading-none font-semibold tracking-wider text-ink-3 uppercase">
            {LABEL[cut.reason]} · {fixture}
          </p>
          <p className="mt-[0.8cqw] text-[3.4cqw] leading-[1.05] font-bold text-balance">
            {why}
          </p>
        </div>
      </div>
      {forWhom && forYou && (
        <div className="ml-[0.7cqw] flex items-stretch">
          <span className="flex shrink-0 items-center bg-air px-[1.6cqw] text-[1.7cqw] font-semibold tracking-wider text-ink-on-fill uppercase">
            For {forWhom}
          </span>
          <p className="flex-1 bg-page/95 px-[1.8cqw] py-[1.1cqw] text-[2.3cqw] leading-tight font-semibold text-ink">
            {forYou}
          </p>
        </div>
      )}
      {atStake && (
        <p className="ml-[0.7cqw] bg-raised/95 px-[2.2cqw] py-[1.2cqw] text-[2.2cqw] leading-tight font-semibold text-ink-2">
          {atStake}
        </p>
      )}
    </motion.div>
  );
}

/** How long the stinger takes to cross the picture, in seconds. */
export const STINGER_S = 0.6;

/**
 * The wipe between matches: a plate crosses the picture with the channel's name, covering the
 * moment the new match's feed starts. Fades instead of sliding when motion is reduced.
 */
export function Stinger({ cutId }: { cutId: string }) {
  const [crossed, setCrossed] = useState<string | null>(null);
  if (crossed === cutId) return null; // gone once it has crossed
  return (
    <motion.div
      key={cutId}
      onAnimationComplete={() => setCrossed(cutId)}
      aria-hidden
      className="pointer-events-none absolute inset-y-0 -left-full z-10 flex w-full items-center justify-center bg-panel"
      initial={{ x: "0%" }}
      animate={{ x: "200%" }}
      transition={{ duration: STINGER_S * 1.6, ease: EASE.smoothOut }}
    >
      <span className="font-broadcast text-[5cqw] font-bold tracking-[0.2em] text-ink uppercase">
        Tiki-Taka
      </span>
    </motion.div>
  );
}
