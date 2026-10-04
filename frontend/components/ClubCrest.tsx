import { type Side, club, useMatch } from "@/lib/match";

const FILL: Record<Side, string> = {
  home: "fill-home",
  away: "fill-away",
};

/** A fictional club's mark: a side-colored roundel with the club initial. */
export function ClubCrest({ side, size = 20 }: { side: Side; size?: number }) {
  const { name } = club(useMatch(), side);
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      role="img"
      aria-label={name}
    >
      <circle cx="12" cy="12" r="11" className={FILL[side]} />
      <circle
        cx="12"
        cy="12"
        r="8.5"
        fill="none"
        className="stroke-ink-on-fill/35"
        strokeWidth="1"
      />
      <text
        x="12"
        y="12.5"
        textAnchor="middle"
        dominantBaseline="middle"
        className="fill-ink-on-fill font-broadcast text-[11px] font-bold"
      >
        {name[0]}
      </text>
    </svg>
  );
}
