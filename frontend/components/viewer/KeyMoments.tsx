import {
  ArrowBendUpRight,
  ArrowsCounterClockwise,
  Cards,
  HandPalm,
  LockSimple,
  SoccerBall,
  Target,
  TrendUp,
} from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";

import { Panel } from "@/components/ui/Panel";
import type { KeyMoment } from "@/lib/contracts.generated";
import { sideOf, useMatch } from "@/lib/match";

const KIND: Record<KeyMoment["kind"], { label: string; Icon: Icon }> = {
  goal: { label: "Goal", Icon: SoccerBall },
  big_chance: { label: "Big chance", Icon: Target },
  save: { label: "Save", Icon: HandPalm },
  red_card: { label: "Red card", Icon: Cards },
  decisive_pass: { label: "Decisive pass", Icon: ArrowBendUpRight },
  ball_won: { label: "Ball won", Icon: ArrowsCounterClockwise },
  momentum_shift: { label: "Momentum", Icon: TrendUp },
};

/**
 * The defining plays so far, newest first. Selecting one shows its receipts: the events behind it
 * light up on the tactical view. Guests see the latest few, without receipts.
 */
export function KeyMoments({
  moments,
  selectedId,
  onSelect,
  receipts,
  hiddenCount = 0,
  className = "",
}: {
  moments: KeyMoment[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  receipts: boolean;
  hiddenCount?: number;
  className?: string;
}) {
  const info = useMatch();
  return (
    <Panel
      title="Key moments"
      aside={
        receipts ? (
          <span className="text-xs text-ink-3">
            Select one to see its receipts
          </span>
        ) : null
      }
      className={className}
    >
      {moments.length === 0 ? (
        <p className="p-3 text-sm text-ink-3">
          Nothing decisive yet. Defining plays appear here as they happen.
        </p>
      ) : (
        <ol className="flex max-h-[420px] flex-col divide-y divide-line overflow-y-auto">
          {moments.map((moment) => {
            const { label, Icon } = KIND[moment.kind];
            const side = sideOf(info, moment.team_id);
            const selected = moment.moment_id === selectedId;
            const content = (
              <>
                <span className="w-8 shrink-0 font-mono text-xs text-ink-3 tabular-nums">
                  {Math.floor(moment.match_clock_ms / 60_000) + 1}&apos;
                </span>
                <span
                  className={`flex size-6 shrink-0 items-center justify-center rounded-md ${side === "home" ? "bg-home/20" : "bg-away/20"}`}
                >
                  <Icon size={14} weight="bold" className="text-ink" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm text-ink">
                    {moment.label}
                  </span>
                  <span className="block text-xs text-ink-3">
                    {label}
                    {receipts &&
                      ` · ${moment.evidence_event_ids.length} ${moment.evidence_event_ids.length === 1 ? "event" : "events"}`}
                  </span>
                </span>
              </>
            );
            return (
              <li key={moment.moment_id}>
                {receipts ? (
                  <button
                    type="button"
                    aria-pressed={selected}
                    onClick={() => onSelect(selected ? null : moment.moment_id)}
                    className={`flex w-full items-center gap-2.5 px-3 py-2 text-left transition-[background-color] duration-150 ease-out focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-air ${selected ? "bg-raised" : "hover:bg-raised/60"}`}
                  >
                    {content}
                  </button>
                ) : (
                  <div className="flex items-center gap-2.5 px-3 py-2">
                    {content}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
      {hiddenCount > 0 && (
        <p className="flex items-center gap-2 border-t border-line px-3 py-2 text-xs text-ink-3">
          <LockSimple size={14} weight="bold" />
          {hiddenCount} earlier {hiddenCount === 1 ? "moment" : "moments"} and
          every receipt with a free account
        </p>
      )}
    </Panel>
  );
}
