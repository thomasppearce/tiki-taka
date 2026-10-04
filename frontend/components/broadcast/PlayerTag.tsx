"use client";

import { motion } from "motion/react";

import { playerHeadPosition } from "@/components/broadcast/SyntheticFeed";
import { SwapText } from "@/components/ui/SwapText";
import { PLAYERS } from "@/lib/mock";
import { DURATION, EASE } from "@/lib/motion";

/**
 * On-air player tag, anchored above the player in the synthetic camera frame: name and number on
 * a plate with a team-color edge, a leader line down to the player. The brief's "real-time player
 * name tagging".
 */
export function PlayerTag({
  playerId,
  line,
}: {
  playerId: string;
  line: string;
}) {
  const player = PLAYERS[playerId];
  const at = playerHeadPosition(playerId);
  if (!player || !at) return null;
  const surname = player.name.split(" ").slice(1).join(" ");
  // Keep the plate inside the frame even when the player is near an edge.
  const left = Math.min(82, Math.max(18, at.x));

  return (
    <motion.div
      className="absolute font-broadcast text-ink uppercase"
      style={{ left: `${left}%`, top: `${at.y}%` }}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{
        opacity: 0,
        transition: { duration: DURATION.medium, ease: EASE.inOut },
      }}
      transition={{ duration: DURATION.slow, ease: EASE.smoothOut }}
    >
      <div className="flex -translate-x-1/2 -translate-y-full flex-col items-center">
        <div className="flex items-stretch">
          <span
            className={`w-[0.6cqw] shrink-0 ${player.team === "t_home" ? "bg-home" : "bg-away"}`}
          />
          <div className="bg-page/95 px-[1.4cqw] py-[1cqw]">
            <p className="text-[2.6cqw] leading-none font-bold whitespace-nowrap">
              <span className="text-ink-3">{player.number}</span> {surname}
            </p>
            <SwapText
              as="p"
              text={line}
              className="mt-[0.5cqw] text-[1.8cqw] leading-none font-semibold whitespace-nowrap text-ink-2"
            />
          </div>
        </div>
        <span className="h-[3cqw] w-[0.15cqw] bg-ink/80" />
      </div>
    </motion.div>
  );
}
