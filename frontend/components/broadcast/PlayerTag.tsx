"use client";

import { motion } from "motion/react";

import { SwapText } from "@/components/ui/SwapText";
import { sideOf, surname, useMatch } from "@/lib/match";
import { DURATION, EASE } from "@/lib/motion";

/**
 * On-air player tag, anchored above the player in the camera frame (`at`, the head position in
 * frame percentages, updated every frame so the tag follows the player): name and number on a
 * plate with a team-color edge, a leader line down to the player. The brief's "real-time player
 * name tagging".
 */
export function PlayerTag({
  playerId,
  line,
  at,
}: {
  playerId: string;
  line: string;
  at: { x: number; y: number };
}) {
  const info = useMatch();
  const player = info.players.get(playerId);
  if (!player) return null;
  const home = sideOf(info, player.club_id) === "home";
  // Near a frame edge, slide only the plate back inside; the leader line stays on the player.
  // The frame is the container, so 1% of its width is 1cqw.
  const plateShift = Math.min(82, Math.max(18, at.x)) - at.x;

  return (
    <motion.div
      className="absolute font-broadcast text-ink uppercase"
      style={{ left: `${at.x}%`, top: `${at.y}%` }}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{
        opacity: 0,
        transition: { duration: DURATION.medium, ease: EASE.inOut },
      }}
      transition={{ duration: DURATION.slow, ease: EASE.smoothOut }}
    >
      <div className="flex -translate-x-1/2 -translate-y-full flex-col items-center">
        <div
          className="flex items-stretch"
          style={{ transform: `translateX(${plateShift}cqw)` }}
        >
          <span
            className={`w-[0.6cqw] shrink-0 ${home ? "bg-home" : "bg-away"}`}
          />
          <div className="bg-page/95 px-[1.4cqw] py-[1cqw]">
            <p className="text-[2.6cqw] leading-none font-bold whitespace-nowrap">
              <span className="text-ink-3">{player.number}</span>{" "}
              {surname(player.name)}
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
