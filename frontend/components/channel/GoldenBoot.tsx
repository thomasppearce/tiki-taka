"use client";

import { motion } from "motion/react";

import { Crest } from "@/components/Crest";
import { Panel } from "@/components/ui/Panel";
import type { GoldenBoot as Boot } from "@/lib/contracts.generated";
import { DURATION, EASE } from "@/lib/motion";

/**
 * The Golden Boot as it stands: the season's goals plus today's, rows sliding as the lead
 * changes, and the latest goal that changed the top of the race.
 */
export function GoldenBoot({
  boot,
  onAirClubIds,
}: {
  boot: Boot;
  /** The clubs in the match on air: their players are marked like the table's rows. */
  onAirClubIds: ReadonlySet<string>;
}) {
  const latest = boot.swings.at(-1);
  return (
    <Panel
      title="Golden Boot"
      aside={<span className="text-xs text-ink-3">League goals</span>}
    >
      <table className="w-full text-sm tabular-nums">
        <caption className="sr-only">
          The league&rsquo;s top scorers as it stands, with today&rsquo;s goals
        </caption>
        <thead className="text-xs text-ink-3">
          <tr className="border-b border-line">
            <th scope="col" className="w-12 py-1.5 pl-3 text-left font-normal">
              Pos
            </th>
            <th scope="col" className="py-1.5 text-left font-normal">
              Player
            </th>
            <th scope="col" className="py-1.5 text-right font-normal">
              Today
            </th>
            <th scope="col" className="w-12 py-1.5 pr-3 text-right font-normal">
              Goals
            </th>
          </tr>
        </thead>
        <tbody>
          {boot.rows.map((row, i) => {
            const shared = boot.rows[i - 1]?.position === row.position;
            const onAir = onAirClubIds.has(row.club.club_id);
            const lead = row.position === 1;
            return (
              <motion.tr
                key={row.player_id}
                layout="position"
                transition={{ duration: DURATION.slow, ease: EASE.smoothOut }}
                className={onAir ? "bg-raised" : ""}
              >
                <td className="relative py-1 pl-3 text-ink-2">
                  {onAir && (
                    <span
                      aria-hidden
                      className="absolute inset-y-0 left-0 w-0.5 bg-air"
                    />
                  )}
                  {shared ? "=" : row.position}
                </td>
                <th scope="row" className="py-1 text-left font-normal">
                  <span className="flex min-w-0 items-center gap-2">
                    <Crest club={row.club} size={18} />
                    <span
                      className={`truncate ${lead ? "font-medium text-ink" : "text-ink-2"}`}
                    >
                      {row.name}
                    </span>
                  </span>
                </th>
                <td className="py-1 text-right font-mono text-xs text-ink-2">
                  {row.today ? `+${row.today}` : ""}
                </td>
                <td className="py-1 pr-3 text-right font-semibold text-ink">
                  {row.goals}
                </td>
              </motion.tr>
            );
          })}
        </tbody>
      </table>
      {latest && (
        <p className="border-t border-line px-3 py-2 text-xs text-ink-2">
          <span className="mr-2 font-mono text-ink-3 tabular-nums">
            {`${Math.floor(latest.match_clock_ms / 60_000) + 1}'`}
          </span>
          {latest.summary}
        </p>
      )}
    </Panel>
  );
}
