import { LockSimple } from "@phosphor-icons/react/dist/ssr";

import { Panel } from "@/components/ui/Panel";
import type { TeamStats } from "@/lib/contracts.generated";
import { useMatch } from "@/lib/match";

type Row = {
  label: string;
  home: number;
  away: number;
  format?: (value: number) => string;
};

const pct = (v: number) => `${Math.round(v)}%`;

function rows(home: TeamStats, away: TeamStats): Row[] {
  return [
    {
      label: "Possession",
      home: home.possession_pct,
      away: away.possession_pct,
      format: pct,
    },
    { label: "Shots", home: home.shots, away: away.shots },
    {
      label: "Expected goals",
      home: home.xg,
      away: away.xg,
      format: (v) => v.toFixed(2),
    },
    {
      label: "On target",
      home: home.shots_on_target,
      away: away.shots_on_target,
    },
    {
      label: "Field tilt",
      home: home.field_tilt_pct,
      away: away.field_tilt_pct,
      format: pct,
    },
    { label: "Passes", home: home.passes, away: away.passes },
    {
      label: "Pass accuracy",
      home: home.pass_accuracy * 100,
      away: away.pass_accuracy * 100,
      format: pct,
    },
    { label: "Tackles", home: home.tackles, away: away.tackles },
    { label: "Fouls", home: home.fouls, away: away.fouls },
    { label: "Offsides", home: home.offsides, away: away.offsides },
    { label: "Yellow cards", home: home.yellow_cards, away: away.yellow_cards },
  ];
}

const GUEST_ROWS = 3;

/**
 * Team stats side by side: each row's numbers in ink, with a thin split bar showing each side's
 * share (home left, away right, a surface gap between them). Guests see the first few rows.
 */
export function StatsPanel({
  home,
  away,
  full,
  className = "",
}: {
  home: TeamStats;
  away: TeamStats;
  full: boolean;
  className?: string;
}) {
  const info = useMatch();
  const all = rows(home, away);
  const shown = full ? all : all.slice(0, GUEST_ROWS);
  return (
    <Panel
      title="Stats"
      aside={
        <span className="flex gap-3 font-mono text-xs text-ink-3">
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-home" aria-hidden />
            {info.home.short}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2 rotate-45 bg-away" aria-hidden />
            {info.away.short}
          </span>
        </span>
      }
      className={className}
    >
      <ul className="flex flex-col gap-3 p-3">
        {shown.map((row) => {
          const format = row.format ?? String;
          const total = row.home + row.away;
          const homeShare = total > 0 ? (row.home / total) * 100 : 50;
          return (
            <li key={row.label} className="flex flex-col gap-1.5">
              <span className="sr-only">
                {row.label}: {info.home.name} {format(row.home)},{" "}
                {info.away.name} {format(row.away)}
              </span>
              <div
                className="flex items-baseline justify-between gap-3 text-sm"
                aria-hidden
              >
                <span className="font-mono text-ink tabular-nums">
                  {format(row.home)}
                </span>
                <span className="text-xs text-ink-3">{row.label}</span>
                <span className="font-mono text-ink tabular-nums">
                  {format(row.away)}
                </span>
              </div>
              <div className="flex h-1 gap-0.5" aria-hidden>
                <div
                  className="rounded-l-sm bg-home"
                  style={{ width: `${homeShare}%` }}
                />
                <div className="flex-1 rounded-r-sm bg-away" />
              </div>
            </li>
          );
        })}
      </ul>
      {!full && (
        <p className="flex items-center gap-2 border-t border-line px-3 py-2 text-xs text-ink-3">
          <LockSimple size={14} weight="bold" />
          {all.length - GUEST_ROWS} more stats with a free account
        </p>
      )}
    </Panel>
  );
}
