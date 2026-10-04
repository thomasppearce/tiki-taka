import { CLUBS, type TeamId } from "@/lib/mock";

const FILL: Record<TeamId, string> = {
  t_home: "fill-home",
  t_away: "fill-away",
};

/** A fictional club's mark: a team-colored roundel with the club initial. */
export function ClubCrest({
  team,
  size = 20,
}: {
  team: TeamId;
  size?: number;
}) {
  const club = CLUBS[team];
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      role="img"
      aria-label={club.name}
    >
      <circle cx="12" cy="12" r="11" className={FILL[team]} />
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
        {club.name[0]}
      </text>
    </svg>
  );
}
