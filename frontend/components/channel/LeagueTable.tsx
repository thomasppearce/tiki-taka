"use client";

import { CaretDown, CaretUp } from "@phosphor-icons/react/dist/ssr";
import { motion } from "motion/react";

import { Crest } from "@/components/Crest";
import { Panel } from "@/components/ui/Panel";
import type {
  LeagueTable as Table,
  MatchCard,
  TableRow,
} from "@/lib/contracts.generated";
import { DURATION, EASE } from "@/lib/motion";

// The last position of each zone: a line under it separates the zones.
const ZONE_ENDS = new Set([1, 4, 17]);

const RESULT_INK: Record<TableRow["result"], string> = {
  winning: "text-ink",
  drawing: "text-ink-2",
  losing: "text-ink-3",
};

/**
 * The league as it stands: the season so far plus today's scores. Rows slide when a goal moves
 * a club; the clubs in the match on air are marked with the on-air spine.
 */
export function LeagueTable({
  table,
  cards,
  onAirMatchId,
}: {
  table: Table;
  cards: ReadonlyMap<string, MatchCard>;
  onAirMatchId: string;
}) {
  return (
    <Panel
      title="As it stands"
      aside={<span className="text-xs text-ink-3">Meridian League</span>}
    >
      <table className="w-full text-sm tabular-nums">
        <caption className="sr-only">
          The Meridian League table as it stands, with today’s scores
        </caption>
        <thead className="text-xs text-ink-3">
          <tr className="border-b border-line">
            <th scope="col" className="w-12 py-1.5 pl-3 text-left font-normal">
              Pos
            </th>
            <th scope="col" className="py-1.5 text-left font-normal">
              Club
            </th>
            <th scope="col" className="py-1.5 text-right font-normal">
              Today
            </th>
            <th scope="col" className="w-10 py-1.5 text-right font-normal">
              GD
            </th>
            <th scope="col" className="w-12 py-1.5 pr-3 text-right font-normal">
              Pts
            </th>
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row) => (
            <Row
              key={row.club.club_id}
              row={row}
              card={cards.get(row.match_id)}
              onAir={row.match_id === onAirMatchId}
            />
          ))}
        </tbody>
      </table>
      <p className="border-t border-line px-3 py-2 text-xs text-ink-3">
        1st champions · 2nd to 4th continental cup · 18th to 20th relegated
      </p>
    </Panel>
  );
}

function Row({
  row,
  card,
  onAir,
}: {
  row: TableRow;
  card: MatchCard | undefined;
  onAir: boolean;
}) {
  const moved = row.start_position - row.position;
  const home = card?.home.club_id === row.club.club_id;
  const today = card
    ? home
      ? `${card.score_home}-${card.score_away}`
      : `${card.score_away}-${card.score_home}`
    : "";
  return (
    <motion.tr
      layout="position"
      transition={{ duration: DURATION.slow, ease: EASE.smoothOut }}
      className={`${ZONE_ENDS.has(row.position) ? "border-b border-line-strong" : ""} ${
        onAir ? "bg-raised" : ""
      }`}
    >
      <td className="relative py-1 pl-3">
        {onAir && (
          <span
            aria-hidden
            className="absolute inset-y-0 left-0 w-0.5 bg-air"
          />
        )}
        <span className="inline-flex items-center gap-1">
          <span className="w-5 text-ink-2">{row.position}</span>
          {moved > 0 && (
            <CaretUp
              size={12}
              weight="bold"
              className="text-ink"
              aria-label={`up ${moved}`}
            />
          )}
          {moved < 0 && (
            <CaretDown
              size={12}
              weight="bold"
              className="text-ink-3"
              aria-label={`down ${-moved}`}
            />
          )}
        </span>
      </td>
      <th scope="row" className="py-1 text-left font-normal">
        <span className="flex min-w-0 items-center gap-2">
          <Crest club={row.club} size={18} />
          <span className={`truncate ${onAir ? "text-ink" : "text-ink-2"}`}>
            {row.club.name}
          </span>
        </span>
      </th>
      <td
        className={`py-1 text-right font-mono text-xs ${RESULT_INK[row.result]}`}
      >
        {today}
      </td>
      <td className="py-1 text-right text-ink-2">
        {row.goal_difference > 0
          ? `+${row.goal_difference}`
          : row.goal_difference}
      </td>
      <td className="py-1 pr-3 text-right font-semibold text-ink">
        {row.points}
      </td>
    </motion.tr>
  );
}
