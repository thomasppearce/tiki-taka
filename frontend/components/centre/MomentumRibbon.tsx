import { area, curveMonotoneX } from "d3-shape";

const FULL_TIME = 90;

/**
 * A match's momentum so far, minute by minute: the home side's spells above the baseline, the
 * away side's below, on a full 90-minute axis so you can see how far in the match is. Position
 * carries who was on top; color only repeats it. Decorative next to the score, so hidden from
 * screen readers (the card's label says who leads).
 */
export function MomentumRibbon({
  momentum,
  height = 28,
  className = "",
}: {
  momentum: number[];
  height?: number;
  className?: string;
}) {
  const width = 360;
  const mid = height / 2;
  const amp = mid - 1.5;
  const span = Math.max(FULL_TIME, momentum.length - 1); // stoppage time stretches it
  const x = (i: number) => (i / span) * width;
  const shape = (sign: 1 | -1) =>
    area<number>()
      .x((_, i) => x(i))
      .y0(mid)
      .y1((v) => mid - Math.max(sign * v, 0) * sign * amp)
      .curve(curveMonotoneX)(momentum) ?? "";
  const now = x(Math.max(momentum.length - 1, 0));

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={`block w-full ${className}`}
      style={{ height }}
      aria-hidden
    >
      <line
        x1={0}
        x2={width}
        y1={mid}
        y2={mid}
        className="stroke-line"
        strokeWidth={1}
        vectorEffect="non-scaling-stroke"
      />
      <path d={shape(1)} className="fill-home/70" />
      <path d={shape(-1)} className="fill-away/70" />
      {momentum.length > 1 && momentum.length <= span && (
        <line
          x1={now}
          x2={now}
          y1={0}
          y2={height}
          className="stroke-ink-3"
          strokeWidth={1}
          vectorEffect="non-scaling-stroke"
        />
      )}
    </svg>
  );
}
