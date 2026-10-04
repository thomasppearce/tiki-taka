import { CLUBS, type TeamId } from "@/lib/mock";

/**
 * On-air lower third with an optional two-team split bar (e.g. possession).
 * Team colors appear only in the bar segments; all text stays in ink.
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
    <div className="absolute bottom-[4.5cqw] left-[3.5cqw] w-[64cqw] font-broadcast text-ink uppercase">
      <div className="flex">
        <div className="w-[0.7cqw] shrink-0 bg-air" />
        <div className="flex-1 bg-page/95 px-[2.2cqw] pt-[1.5cqw] pb-[1.6cqw]">
          <p className="text-[1.9cqw] leading-none font-semibold tracking-wider text-ink-3">
            {label}
          </p>
          <p className="mt-[0.7cqw] text-[4.4cqw] leading-none font-bold">
            {headline}
          </p>
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
    </div>
  );
}
