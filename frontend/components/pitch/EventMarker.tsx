import type { MatchEvent } from "@/lib/contracts.generated";
import { toPitch } from "@/lib/pitch";

/**
 * One event on the pitch, in meters. Shape carries team identity alongside color (home circle,
 * away diamond) so the encoding never relies on color alone. A 2px surface ring separates
 * overlapping marks; cited events get an on-air ring.
 */
export function EventMarker({
  event,
  cited,
  dimmed,
}: {
  event: MatchEvent;
  cited: boolean;
  dimmed: boolean;
}) {
  if (!event.location) return null;
  const start = toPitch(event.location);
  const end = event.end_location ? toPitch(event.end_location) : null;
  const isHome = event.team_id === "t_home";
  const teamFill = isHome ? "fill-home" : "fill-away";
  const teamStroke = isHome ? "stroke-home" : "stroke-away";

  return (
    <g opacity={dimmed ? 0.3 : 1}>
      {end && (
        <>
          <line
            x1={start.x}
            y1={start.y}
            x2={end.x}
            y2={end.y}
            className={teamStroke}
            strokeWidth={1.5}
            strokeOpacity={0.7}
            strokeDasharray={event.type === "sprint" ? "3 3" : undefined}
            vectorEffect="non-scaling-stroke"
          />
          <circle cx={end.x} cy={end.y} r={0.45} className={teamFill} />
        </>
      )}
      {cited && (
        <circle
          cx={start.x}
          cy={start.y}
          r={2.6}
          fill="none"
          className="stroke-air"
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
      )}
      {isHome ? (
        <circle
          cx={start.x}
          cy={start.y}
          r={1.3}
          className={`${teamFill} stroke-panel`}
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
      ) : (
        <rect
          x={start.x - 1.15}
          y={start.y - 1.15}
          width={2.3}
          height={2.3}
          transform={`rotate(45 ${start.x} ${start.y})`}
          className={`${teamFill} stroke-panel`}
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
      )}
    </g>
  );
}
