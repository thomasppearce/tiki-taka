import type { MatchEvent } from "@/lib/contracts.generated";
import { toPitch } from "@/lib/pitch";

const FADE = "opacity var(--duration-fast) var(--ease-smooth-out)";

/**
 * One event on the pitch, in meters: a small mark where it happened and, for passes and sprints,
 * a line to where it ended. Shape carries team identity alongside color (home circle, away
 * diamond) so the encoding never relies on color alone. Kept smaller than the player markers.
 * `opacity` fades older events; cited events get an on-air ring.
 */
export function EventMarker({
  event,
  cited,
  opacity,
}: {
  event: MatchEvent;
  cited: boolean;
  opacity: number;
}) {
  if (!event.location) return null;
  const start = toPitch(event.location);
  const end = event.end_location ? toPitch(event.end_location) : null;
  const isHome = event.team_id === "t_home";
  const teamFill = isHome ? "fill-home" : "fill-away";
  const teamStroke = isHome ? "stroke-home" : "stroke-away";

  return (
    <g style={{ opacity, transition: FADE }}>
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
      {/* Always rendered so the ring can scale in and fade out as the selection changes. */}
      <circle
        cx={start.x}
        cy={start.y}
        r={2}
        fill="none"
        className="stroke-air"
        strokeWidth={2}
        vectorEffect="non-scaling-stroke"
        style={{
          opacity: cited ? 1 : 0,
          transform: cited ? "scale(1)" : "scale(0.5)",
          transformBox: "fill-box",
          transformOrigin: "center",
          transition: `${FADE}, transform var(--duration-fast) var(--ease-smooth-out)`,
        }}
      />
      {isHome ? (
        <circle
          cx={start.x}
          cy={start.y}
          r={0.85}
          className={`${teamFill} stroke-panel`}
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
      ) : (
        <rect
          x={start.x - 0.75}
          y={start.y - 0.75}
          width={1.5}
          height={1.5}
          transform={`rotate(45 ${start.x} ${start.y})`}
          className={`${teamFill} stroke-panel`}
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
      )}
    </g>
  );
}
