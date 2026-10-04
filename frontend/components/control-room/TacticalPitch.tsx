"use client";

import { EventMarker } from "@/components/pitch/EventMarker";
import { PitchMarkings } from "@/components/pitch/PitchMarkings";
import { Panel } from "@/components/ui/Panel";
import type { MatchEvent, TrackingFrame } from "@/lib/contracts.generated";
import type { FrameSource } from "@/lib/live/useLiveMatch";
import { type MatchInfo, sideOf, useMatch } from "@/lib/match";
import { PITCH_VIEWBOX, toPitch } from "@/lib/pitch";
import { useMatchFrame } from "@/lib/useMatchFrame";

const TRAIL = 12;

/**
 * Top-down formation board: every player and the ball from the same tracking frame as the program
 * camera, over a fading trail of the latest actions. When a proposal is selected, the events it
 * cites keep an on-air ring (even once they are older than the trail) and the rest recede: the
 * evidence view.
 */
export function TacticalPitch({
  events,
  citedEventIds,
  source,
  className,
}: {
  events: MatchEvent[];
  citedEventIds: ReadonlySet<string>;
  source: FrameSource;
  className?: string;
}) {
  const info = useMatch();
  const frame = useMatchFrame(source);
  const minute = frame
    ? `${Math.floor(frame.match_clock_ms / 60_000)}'`
    : "kickoff";
  const hasSelection = citedEventIds.size > 0;
  const trail = events.slice(-TRAIL);
  const olderCited = events
    .slice(0, -TRAIL)
    .filter((e) => citedEventIds.has(e.event_id));

  return (
    <Panel title="Tactical view" aside={<Legend />} className={className}>
      <div className="flex flex-1 items-center p-3">
        <svg
          viewBox={PITCH_VIEWBOX}
          className="w-full"
          role="img"
          aria-label={`Formations at ${minute}, the last ${trail.length} actions, and ${citedEventIds.size} events cited by the selected proposal`}
        >
          <PitchMarkings />
          {[...olderCited, ...trail].map((event) => {
            const cited = citedEventIds.has(event.event_id);
            const age = trail.indexOf(event);
            const recency =
              age < 0 ? 1 : 0.3 + (0.7 * (age + 1)) / trail.length;
            const opacity = cited ? 1 : hasSelection ? recency * 0.35 : recency;
            return (
              <EventMarker
                key={event.event_id}
                event={event}
                cited={cited}
                opacity={opacity}
              />
            );
          })}
          {frame?.players.map((player) => (
            <PlayerDot key={player.player_id} player={player} info={info} />
          ))}
          {frame && <Ball frame={frame} />}
        </svg>
      </div>
    </Panel>
  );
}

function PlayerDot({
  player,
  info,
}: {
  player: TrackingFrame["players"][number];
  info: MatchInfo;
}) {
  const at = toPitch(player);
  const home = sideOf(info, player.team_id) === "home";
  const number = info.players.get(player.player_id)?.number;
  return (
    <g data-player={player.player_id} data-x={at.x} data-y={at.y}>
      {home ? (
        <circle
          cx={at.x}
          cy={at.y}
          r={1.9}
          className="fill-home stroke-panel"
          strokeWidth={1.5}
          vectorEffect="non-scaling-stroke"
        />
      ) : (
        <rect
          x={at.x - 1.6}
          y={at.y - 1.6}
          width={3.2}
          height={3.2}
          rx={0.3}
          transform={`rotate(45 ${at.x} ${at.y})`}
          className="fill-away stroke-panel"
          strokeWidth={1.5}
          vectorEffect="non-scaling-stroke"
        />
      )}
      <text
        x={at.x}
        y={at.y}
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={1.8}
        className="fill-ink-on-fill font-semibold"
      >
        {number}
      </text>
    </g>
  );
}

function Ball({ frame }: { frame: TrackingFrame }) {
  const at = toPitch(frame.ball);
  return (
    <circle
      cx={at.x}
      cy={at.y}
      r={0.8}
      className="fill-ink stroke-page"
      strokeWidth={1.5}
      vectorEffect="non-scaling-stroke"
    />
  );
}

function Legend() {
  const { home, away } = useMatch();
  return (
    <ul className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-3">
      <li className="flex items-center gap-1.5">
        <span className="size-2 rounded-full bg-home" aria-hidden />
        {home.short}
      </li>
      <li className="flex items-center gap-1.5">
        <span className="size-2 rotate-45 bg-away" aria-hidden />
        {away.short}
      </li>
      <li className="flex items-center gap-1.5">
        <span className="size-1.5 rounded-full bg-ink" aria-hidden />
        Ball
      </li>
      <li className="flex items-center gap-1.5">
        <span
          className="size-2.5 rounded-full border-2 border-air"
          aria-hidden
        />
        Cited
      </li>
    </ul>
  );
}
