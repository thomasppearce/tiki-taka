"use client";

import { AnimatePresence } from "motion/react";

import { PlayerTag } from "@/components/broadcast/PlayerTag";
import {
  type Homography,
  type Point,
  arcPoints,
  project,
  projectPath,
  scaleAt,
  solveHomography,
} from "@/lib/camera";
import type { TrackingFrame } from "@/lib/contracts.generated";
import { cameraTargetAt } from "@/lib/matchSim";
import { PITCH, toPitch } from "@/lib/pitch";

const W = 1600;
const H = 900;
const STANDS = 0.17 * H;
const { length: L, width: PW } = PITCH;
const MID = PW / 2;
const STRIPES = 12;

/**
 * The main camera aimed at pitch x = `centre` (meters). Both edges are centered on the aim point
 * so the horizon stays level; the far touchline spans 76m of screen and the near edge 48m over
 * 1.36 screen widths, a ~2.2x perspective ratio like a high halfway-line camera.
 */
function cameraAt(centre: number): Homography {
  return solveHomography([
    { pitch: { x: centre - 38, y: 0 }, screen: { x: 0, y: STANDS } },
    { pitch: { x: centre + 38, y: 0 }, screen: { x: W, y: STANDS } },
    { pitch: { x: centre + 24, y: 70 }, screen: { x: W * 1.18, y: H } },
    { pitch: { x: centre - 24, y: 70 }, screen: { x: W * -0.18, y: H } },
  ]);
}

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

export type CameraTag = { id: string; playerId: string; line: string };

/**
 * The program monitor's camera on the synthetic match. Real footage is off-limits, so it renders
 * the tracking frame through a broadcast camera model that pans to follow play. An on-air player
 * tag rides above its player as he moves.
 */
export function LiveCamera({
  frame,
  tag,
}: {
  frame: TrackingFrame;
  tag: CameraTag | null;
}) {
  const centre = clampCentre((cameraTargetAt(frame.match_clock_ms) / 100) * L);
  const camera = cameraAt(centre);
  const players = frame.players
    .map((p) => ({ ...p, at: toPitch(p) }))
    .sort((a, b) => a.at.y - b.at.y); // far players first so nearer ones overlap them
  const tagged = tag && players.find((p) => p.player_id === tag.playerId);
  const head = tagged ? headPosition(camera, tagged.at) : null;
  // A tag only makes sense while its player is in shot; the margin stops it flickering when
  // the player hovers at the frame edge.
  const inShot = head !== null && head.x > -6 && head.x < 106;

  return (
    <>
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
                camera,
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
            <path key={i} d={projectPath(camera, line.points, line.close)} />
          ))}
        </g>

        {players.map((player) => (
          <PlayerFigure
            key={player.player_id}
            camera={camera}
            at={player.at}
            home={player.team_id === "t_home"}
          />
        ))}

        <BallMarker camera={camera} at={toPitch(frame.ball)} />
      </svg>

      <AnimatePresence>
        {tag && head && inShot && (
          <PlayerTag
            key={tag.id}
            playerId={tag.playerId}
            line={tag.line}
            at={head}
          />
        )}
      </AnimatePresence>
    </>
  );
}

/** Keep the frame on the pitch: the camera never aims past either penalty box. */
function clampCentre(x: number): number {
  return Math.min(81, Math.max(24, x));
}

/** A player's head in the frame, as percentages, for anchoring tags. */
function headPosition(camera: Homography, at: Point): { x: number; y: number } {
  const foot = project(camera, at);
  const head = foot.y - 1.85 * scaleAt(camera, at);
  return { x: (foot.x / W) * 100, y: (head / H) * 100 };
}

function PlayerFigure({
  camera,
  at,
  home,
}: {
  camera: Homography;
  at: Point;
  home: boolean;
}) {
  const foot = project(camera, at);
  const s = scaleAt(camera, at);
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
        className={`${home ? "fill-home" : "fill-away"} stroke-page`}
        strokeWidth={Math.max(1, 0.12 * s)}
      />
    </g>
  );
}

function BallMarker({ camera, at }: { camera: Homography; at: Point }) {
  const ground = project(camera, at);
  const s = scaleAt(camera, at);
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
