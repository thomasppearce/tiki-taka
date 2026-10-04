"use client";

import { motion } from "motion/react";

import { SwapText } from "@/components/ui/SwapText";
import { CLUBS, type TeamId } from "@/lib/mock";
import { DURATION, EASE } from "@/lib/motion";

/**
 * On-air lower third. Wipes in left to right behind the on-air spine like a broadcast graphic,
 * the headline rises in after the plate, and it fades out. Team colors appear only in the split
 * bar; text stays in ink.
 */
export function LowerThird({
  label,
  headline,
  split,
  splitLabel,
}: {
  label: string;
  headline: string;
  split?: Record<TeamId, number>;
  splitLabel?: string;
}) {
  return (
    <motion.div
      className="absolute bottom-[4.5cqw] left-[3.5cqw] w-max max-w-[86cqw] min-w-[48cqw] font-broadcast text-ink uppercase"
      initial={{ clipPath: "inset(0 100% 0 0)" }}
      animate={{ clipPath: "inset(0 0% 0 0)" }}
      exit={{
        opacity: 0,
        transition: { duration: DURATION.medium, ease: EASE.inOut },
      }}
      transition={{ duration: DURATION.verySlow, ease: EASE.smoothOut }}
    >
      <div className="flex">
        <div className="w-[0.7cqw] shrink-0 bg-air" />
        <div className="flex-1 bg-page/95 px-[2.2cqw] pt-[1.5cqw] pb-[1.6cqw]">
          <p className="text-[1.9cqw] leading-none font-semibold tracking-wider text-ink-3">
            {label}
          </p>
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: DURATION.slow,
              ease: EASE.smoothOut,
              delay: DURATION.quick,
            }}
          >
            <SwapText
              as="p"
              text={headline}
              className="mt-[0.7cqw] text-[4.4cqw] leading-none font-bold"
            />
          </motion.div>
        </div>
      </div>
      {split && (
        <div className="ml-[0.7cqw] flex items-center gap-[1.4cqw] bg-raised/95 px-[2.2cqw] py-[1.2cqw] text-[2cqw] leading-none font-semibold tabular-nums">
          <span className="tracking-wider text-ink-3">{splitLabel}</span>
          <span>
            {CLUBS.t_away.short} {split.t_away}%
          </span>
          <div className="flex h-[0.9cqw] flex-1 gap-[0.25cqw]">
            <div className="bg-away" style={{ width: `${split.t_away}%` }} />
            <div className="flex-1 bg-home" />
          </div>
          <span>
            {split.t_home}% {CLUBS.t_home.short}
          </span>
        </div>
      )}
    </motion.div>
  );
}
