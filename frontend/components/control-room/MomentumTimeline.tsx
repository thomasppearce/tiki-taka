import {
  Diamond,
  MonitorPlay,
  SoccerBall,
} from "@phosphor-icons/react/dist/ssr";
import { area, curveMonotoneX, line } from "d3-shape";

import { Panel } from "@/components/ui/Panel";
import { CLUBS, type TimelineMarker } from "@/lib/mock";

const FULL_TIME = 90;
const VIEW_W = 900;
const VIEW_H = 100;
const MID = VIEW_H / 2;
const AMPLITUDE = 44;
const TICKS = [0, 15, 30, 45, 60, 75, 90];

const x = (minute: number) => (minute / FULL_TIME) * VIEW_W;
const pct = (minute: number) => `${(minute / FULL_TIME) * 100}%`;

/**
 * Momentum per minute: Northgate above the baseline, Westmere below. Position carries who is on
 * top; team color only repeats the identity the pitch already uses.
 */
export function MomentumTimeline({
  momentum,
  markers,
  nowMinute,
}: {
  momentum: number[];
  markers: TimelineMarker[];
  nowMinute: number;
}) {
  const shape = (sign: 1 | -1) => {
    const y = (v: number) => MID - Math.max(sign * v, 0) * sign * AMPLITUDE;
    // Draw a team's edge only while it is on top, plus one neighbor each side so the line
    // meets the baseline instead of running along it in team color.
    const onTop = (v: number | undefined) => v !== undefined && sign * v > 0;
    return {
      fill: area<number>()
        .x((_, i) => x(i))
        .y0(MID)
        .y1(y)
        .curve(curveMonotoneX)(momentum),
      edge: line<number>()
        .defined(
          (v, i, all) => onTop(v) || onTop(all[i - 1]) || onTop(all[i + 1]),
        )
        .x((_, i) => x(i))
        .y(y)
        .curve(curveMonotoneX)(momentum),
    };
  };
  const home = shape(1);
  const away = shape(-1);

  return (
    <Panel title="Momentum" aside={<Legend />}>
      <div className="px-4 pt-2 pb-3">
        <div className="relative h-5" aria-hidden>
          {markers.map((marker) => (
            <MarkerIcon
              key={`${marker.kind}-${marker.minute}`}
              marker={marker}
            />
          ))}
        </div>

        <div className="relative h-20">
          <svg
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            preserveAspectRatio="none"
            className="absolute inset-0 size-full overflow-visible"
            role="img"
            aria-label={`Momentum chart up to minute ${nowMinute}`}
          >
            <line
              x1={x(45)}
              x2={x(45)}
              y1={0}
              y2={VIEW_H}
              className="stroke-line"
              strokeDasharray="3 3"
              vectorEffect="non-scaling-stroke"
            />
            <path d={home.fill ?? ""} className="fill-home/35" />
            <path d={away.fill ?? ""} className="fill-away/35" />
            <path
              d={home.edge ?? ""}
              fill="none"
              className="stroke-home"
              strokeWidth={2}
              vectorEffect="non-scaling-stroke"
            />
            <path
              d={away.edge ?? ""}
              fill="none"
              className="stroke-away"
              strokeWidth={2}
              vectorEffect="non-scaling-stroke"
            />
            <line
              x1={0}
              x2={VIEW_W}
              y1={MID}
              y2={MID}
              className="stroke-line-strong"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
          <div
            className="absolute inset-y-0 right-0 bg-page/45"
            style={{ left: pct(nowMinute) }}
            aria-hidden
          />
          <div
            className="absolute inset-y-0 w-px bg-ink"
            style={{ left: pct(nowMinute) }}
          >
            <span className="absolute -top-0.5 left-1.5 font-mono text-xs text-ink tabular-nums">
              {nowMinute}&apos;
            </span>
          </div>
        </div>

        <div className="relative mt-1.5 h-4 font-mono text-xs text-ink-3 tabular-nums">
          {TICKS.map((minute) => (
            <span
              key={minute}
              className="absolute -translate-x-1/2 first:translate-x-0 last:-translate-x-full"
              style={{ left: pct(minute) }}
            >
              {minute === 45 ? "HT" : `${minute}'`}
            </span>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function MarkerIcon({ marker }: { marker: TimelineMarker }) {
  const style = { left: pct(marker.minute) };
  const common = "absolute top-0.5 -translate-x-1/2";
  if (marker.kind === "goal") {
    return (
      <span
        className={`${common} flex items-center gap-1`}
        style={style}
        title={marker.label}
      >
        <SoccerBall size={14} className="text-ink-2" />
        <span
          className={`size-1.5 rounded-full ${marker.team === "t_away" ? "bg-away" : "bg-home"}`}
        />
      </span>
    );
  }
  if (marker.kind === "aired") {
    return (
      <span className={common} style={style} title={marker.label}>
        <MonitorPlay size={14} className="text-ink-3" />
      </span>
    );
  }
  return (
    <span className={common} style={style} title={marker.label}>
      <Diamond size={12} weight="fill" className="text-air" />
    </span>
  );
}

function Legend() {
  return (
    <ul className="flex items-center gap-3 text-xs text-ink-3">
      <li className="flex items-center gap-1.5">
        <span className="h-2 w-3 bg-home" aria-hidden />
        {CLUBS.t_home.name} on top
      </li>
      <li className="flex items-center gap-1.5">
        <span className="h-2 w-3 bg-away" aria-hidden />
        {CLUBS.t_away.name} on top
      </li>
      <li className="flex items-center gap-1.5">
        <Diamond size={10} weight="fill" className="text-air" aria-hidden />
        Moment detected
      </li>
      <li className="flex items-center gap-1.5">
        <MonitorPlay size={12} aria-hidden />
        Aired
      </li>
    </ul>
  );
}
