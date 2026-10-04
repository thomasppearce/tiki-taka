import { PITCH } from "@/lib/pitch";

const { length: L, width: W } = PITCH;
const MID_Y = W / 2;
const BOX = { depth: 16.5, half: 20.16 };
const SIX = { depth: 5.5, half: 9.16 };
const SPOT = 11;
const ARC_R = 9.15;
// Where the penalty arc meets the box edge: 9.15m circle around the spot, cut at 16.5m.
const ARC_DY = Math.sqrt(ARC_R ** 2 - (BOX.depth - SPOT) ** 2);
const STRIPES = 12;

/** Pitch surface and markings as an SVG group, in meters. Strokes stay 1px at any scale. */
export function PitchMarkings() {
  return (
    <g>
      {Array.from({ length: STRIPES }, (_, i) => (
        <rect
          key={i}
          x={(i * L) / STRIPES}
          y={0}
          width={L / STRIPES}
          height={W}
          className={i % 2 ? "fill-pitch-stripe" : "fill-pitch"}
        />
      ))}
      {/* vector-effect is not inherited, so each mark sets it to keep strokes at 1px. */}
      <g fill="none" className="stroke-line-strong" strokeWidth={1}>
        <rect
          x={0}
          y={0}
          width={L}
          height={W}
          vectorEffect="non-scaling-stroke"
        />
        <line
          x1={L / 2}
          y1={0}
          x2={L / 2}
          y2={W}
          vectorEffect="non-scaling-stroke"
        />
        <circle
          cx={L / 2}
          cy={MID_Y}
          r={ARC_R}
          vectorEffect="non-scaling-stroke"
        />
        {[0, L].map((goalLine) => {
          const dir = goalLine === 0 ? 1 : -1;
          const boxEdge = goalLine + dir * BOX.depth;
          return (
            <g key={goalLine}>
              <rect
                x={Math.min(goalLine, boxEdge)}
                y={MID_Y - BOX.half}
                width={BOX.depth}
                height={BOX.half * 2}
                vectorEffect="non-scaling-stroke"
              />
              <rect
                x={Math.min(goalLine, goalLine + dir * SIX.depth)}
                y={MID_Y - SIX.half}
                width={SIX.depth}
                height={SIX.half * 2}
                vectorEffect="non-scaling-stroke"
              />
              <path
                d={`M ${boxEdge} ${MID_Y - ARC_DY} A ${ARC_R} ${ARC_R} 0 0 ${dir === 1 ? 1 : 0} ${boxEdge} ${MID_Y + ARC_DY}`}
                vectorEffect="non-scaling-stroke"
              />
              <rect
                x={goalLine === 0 ? -1.6 : L}
                y={MID_Y - 3.66}
                width={1.6}
                height={7.32}
                vectorEffect="non-scaling-stroke"
              />
            </g>
          );
        })}
      </g>
      <g className="fill-line-strong">
        <circle cx={L / 2} cy={MID_Y} r={0.35} />
        <circle cx={SPOT} cy={MID_Y} r={0.3} />
        <circle cx={L - SPOT} cy={MID_Y} r={0.3} />
      </g>
    </g>
  );
}
