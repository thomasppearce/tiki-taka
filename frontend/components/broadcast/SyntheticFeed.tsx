import { memo } from "react";

import {
  arcPoints,
  project,
  projectPath,
  scaleAt,
  solveHomography,
  type Point,
} from "@/lib/camera";
import { FEED_SNAPSHOT } from "@/lib/mock";
import { PITCH, toPitch } from "@/lib/pitch";

const W = 1600;
const H = 900;
const STANDS = 0.17 * H;
const { length: L, width: PW } = PITCH;
const MID = PW / 2;

// Main-camera framing on the left third, where play is. Both edges are centered on x = 22m so
// the horizon stays level; the far touchline spans 76m of screen width and the near edge 48m
// (over 1.36 screen widths), a ~2.2x perspective ratio like a high halfway-line camera.
const CAMERA = solveHomography([
  { pitch: { x: -16, y: 0 }, screen: { x: 0, y: STANDS } },
  { pitch: { x: 60, y: 0 }, screen: { x: W, y: STANDS } },
  { pitch: { x: 46, y: 70 }, screen: { x: W * 1.18, y: H } },
  { pitch: { x: -2, y: 70 }, screen: { x: W * -0.18, y: H } },
]);

const STRIPES = 12;

/** Pitch lines in meters, as polylines to project. */
const LINES: { points: Point[]; close?: boolean }[] = [
  {
    points: [
      { x: 0, y: 0 },
      { x: L, y: 0 },
      { x: L, y: PW },
      { x: 0, y: PW },
    ],
    close: true,
  },
  {
    points: [
      { x: L / 2, y: 0 },
      { x: L / 2, y: PW },
    ],
  },
  { points: arcPoints({ x: L / 2, y: MID }, 9.15) },
  ...[0, L].flatMap((goal) => {
    const dir = goal === 0 ? 1 : -1;
    const box = (depth: number, half: number) => ({
      points: [
        { x: goal, y: MID - half },
        { x: goal + dir * depth, y: MID - half },
        { x: goal + dir * depth, y: MID + half },
        { x: goal, y: MID + half },
      ],
    });
    const spot = { x: goal + dir * 11, y: MID };
    const cut = Math.acos(5.5 / 9.15);
    const arc =
      dir === 1
        ? arcPoints(spot, 9.15, -cut, cut, 24)
        : arcPoints(spot, 9.15, Math.PI - cut, Math.PI + cut, 24);
    return [box(16.5, 20.16), box(5.5, 9.16), { points: arc }];
  }),
];

/**
 * The program monitor's camera. Real footage is off-limits, so this renders the synthetic match
 * through a broadcast camera model: pitch and stripes in true perspective, upright players.
 */
// Memoized: the camera frame is static, so it never needs to re-render with the clock.
export const SyntheticFeed = memo(function SyntheticFeed() {
  const players = [...FEED_SNAPSHOT.players]
    .map((p) => ({ ...p, at: toPitch(p) }))
    .sort((a, b) => a.at.y - b.at.y); // far players first so near players overlap them
  const ball = toPitch(FEED_SNAPSHOT.ball);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="absolute inset-0 size-full"
      aria-hidden
    >
      <rect width={W} height={STANDS} className="fill-raised" />
      <rect y={STANDS - 14} width={W} height={14} className="fill-line" />

      {Array.from({ length: STRIPES }, (_, i) => {
        const x0 = (i * L) / STRIPES;
        const x1 = ((i + 1) * L) / STRIPES;
        return (
          <path
            key={i}
            d={projectPath(
              CAMERA,
              [
                { x: x0, y: 0 },
                { x: x1, y: 0 },
                { x: x1, y: PW + 6 },
                { x: x0, y: PW + 6 },
              ],
              true,
            )}
            className={i % 2 ? "fill-pitch-stripe" : "fill-pitch"}
          />
        );
      })}

      <g fill="none" className="stroke-line-strong" strokeWidth={2.5}>
        {LINES.map((line, i) => (
          <path key={i} d={projectPath(CAMERA, line.points, line.close)} />
        ))}
      </g>

      {players.map((player, i) => (
        <PlayerFigure key={i} at={player.at} team={player.team} />
      ))}

      <BallMarker at={ball} />
    </svg>
  );
});

function PlayerFigure({ at, team }: { at: Point; team: "t_home" | "t_away" }) {
  const foot = project(CAMERA, at);
  const s = scaleAt(CAMERA, at);
  const bodyW = 0.75 * s;
  const bodyH = 1.85 * s;
  return (
    <g>
      <ellipse
        cx={foot.x}
        cy={foot.y}
        rx={0.7 * s}
        ry={0.22 * s}
        className="fill-page/70"
      />
      <rect
        x={foot.x - bodyW / 2}
        y={foot.y - bodyH}
        width={bodyW}
        height={bodyH}
        rx={bodyW / 2}
        className={`${team === "t_home" ? "fill-home" : "fill-away"} stroke-page`}
        strokeWidth={Math.max(1, 0.12 * s)}
      />
    </g>
  );
}

function BallMarker({ at }: { at: Point }) {
  const ground = project(CAMERA, at);
  const s = scaleAt(CAMERA, at);
  return (
    <g>
      <ellipse
        cx={ground.x}
        cy={ground.y}
        rx={0.3 * s}
        ry={0.1 * s}
        className="fill-page/70"
      />
      <circle
        cx={ground.x}
        cy={ground.y - 0.35 * s}
        r={0.24 * s}
        className="fill-ink"
      />
    </g>
  );
}

/**
 * Where a player's head sits in the program frame, as percentages of the frame. Used to anchor
 * on-air player tags to the player. Null if the player is not in the camera snapshot.
 */
export function playerHeadPosition(
  playerId: string,
): { x: number; y: number } | null {
  const player = FEED_SNAPSHOT.players.find((p) => p.id === playerId);
  if (!player) return null;
  const at = toPitch(player);
  const foot = project(CAMERA, at);
  const head = foot.y - 1.85 * scaleAt(CAMERA, at);
  return { x: (foot.x / W) * 100, y: (head / H) * 100 };
}
