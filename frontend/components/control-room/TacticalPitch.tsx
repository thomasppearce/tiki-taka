"use client";

import { ArrowLeft, ArrowRight } from "@phosphor-icons/react/dist/ssr";

import { EventMarker } from "@/components/pitch/EventMarker";
import { PitchMarkings } from "@/components/pitch/PitchMarkings";
import { Panel } from "@/components/ui/Panel";
import { SwapText } from "@/components/ui/SwapText";
import type { MatchEvent, TrackingFrame } from "@/lib/contracts.generated";
import type { FrameSource } from "@/lib/live/useLiveMatch";
import { type MatchInfo, club, sideOf, useMatch } from "@/lib/match";
import { PITCH_VIEWBOX, toPitch } from "@/lib/pitch";
import { useMatchFrame } from "@/lib/useMatchFrame";

/** How long a pass or shot stays drawn after the ball is struck, fading out as it goes. */
const TRAIL_MS = 8_000;
const TRAIL_TYPES: ReadonlySet<string> = new Set(["pass", "shot"]);
/** The events that say what is happening now: live play, or a stoppage and why. */
const STATE_TYPES: ReadonlySet<string> = new Set([
  "pass",
  "shot",
  "tackle",
  "kickoff",
  "throw_in",
  "goal_kick",
  "corner",
  "free_kick",
  "penalty",
  "goal",
  "half_end",
]);

/**
 * Top-down formation board: every player and the ball from the same tracking frame as the program
 * camera. A pass or shot is drawn the moment the ball is struck and fades over eight seconds, so
 * the lines always match the play; a stoppage says what it is (goal kick, corner...). When a
 * proposal or moment is selected, the events it cites are drawn with an on-air ring whatever
 * their age, and the live trail recedes: the evidence view.
 */
export function TacticalPitch({
  events,
  citedEventIds,
  source,
  focusPlayerId = null,
  className,
}: {
  events: MatchEvent[];
  citedEventIds: ReadonlySet<string>;
  source: FrameSource;
  /** A player the viewer follows: ringed on the board. */
  focusPlayerId?: string | null;
  className?: string;
}) {
  const info = useMatch();
  const frame = useMatchFrame(source);
  const now = frame?.match_clock_ms ?? events.at(-1)?.match_clock_ms ?? 0;
  const seen = events.filter((e) => e.match_clock_ms <= now);
  const hasSelection = citedEventIds.size > 0;
  const trail = seen.filter(
    (e) =>
      TRAIL_TYPES.has(e.type) &&
      now - e.match_clock_ms < TRAIL_MS &&
      !citedEventIds.has(e.event_id),
  );
  const cited = seen.filter((e) => citedEventIds.has(e.event_id));
  const situation = describeSituation(seen, info);

  return (
    <Panel title="Tactical view" aside={<Legend />} className={className}>
      <div className="flex flex-1 flex-col justify-center gap-2 p-3">
        <div className="relative">
          <svg
            viewBox={PITCH_VIEWBOX}
            className="w-full"
            role="img"
            aria-label={`Formations at ${Math.floor(now / 60_000) + 1}', ${situation ?? "ball in play"}, with passes and shots from the last eight seconds${hasSelection ? ` and ${cited.length} cited events` : ""}`}
          >
            <PitchMarkings />
            {trail.map((event) => {
              const fresh = 1 - (now - event.match_clock_ms) / TRAIL_MS;
              return (
                <EventMarker
                  key={event.event_id}
                  event={event}
                  cited={false}
                  opacity={(hasSelection ? 0.25 : 1) * Math.max(fresh, 0)}
                />
              );
            })}
            {cited.map((event) => (
              <EventMarker
                key={event.event_id}
                event={event}
                cited
                opacity={1}
              />
            ))}
            {frame?.players.map((player) => (
              <PlayerDot
                key={player.player_id}
                player={player}
                info={info}
                focused={player.player_id === focusPlayerId}
              />
            ))}
            {frame && <Ball frame={frame} />}
          </svg>
          {situation && (
            <SwapText
              as="p"
              text={situation}
              className="absolute top-2 left-1/2 -translate-x-1/2 rounded-md bg-page/90 px-2 py-1 text-xs font-medium whitespace-nowrap text-ink"
            />
          )}
        </div>
        <div className="flex justify-between text-xs text-ink-3">
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-home" aria-hidden />
            {info.home.short} attack
            <ArrowRight size={12} weight="bold" aria-label="to the right" />
          </span>
          <span className="flex items-center gap-1.5">
            <ArrowLeft size={12} weight="bold" aria-label="to the left" />
            {info.away.short} attack
            <span className="size-2 rotate-45 bg-away" aria-hidden />
          </span>
        </div>
      </div>
    </Panel>
  );
}

/** What is happening, if the ball is dead: "Goal kick · WMA", "Half-time"... Null in play. */
function describeSituation(
  events: MatchEvent[],
  info: MatchInfo,
): string | null {
  let index = events.length - 1;
  while (index >= 0 && !STATE_TYPES.has(events[index].type)) index -= 1;
  const latest = events[index];
  if (!latest) return null;
  const short = club(info, sideOf(info, latest.team_id)).short;
  const before = events
    .slice(0, index)
    .reverse()
    .find(
      (e) => e.type === "offside" || e.type === "foul" || e.type === "pass",
    );
  switch (latest.type) {
    case "throw_in":
      return `Throw-in · ${short}`;
    case "goal_kick":
      return `Goal kick · ${short}`;
    case "corner":
      return `Corner · ${short}`;
    case "free_kick":
      if (before?.type === "offside") return `Offside · free kick ${short}`;
      if (before?.type === "foul") return `Foul · free kick ${short}`;
      return `Free kick · ${short}`;
    case "penalty":
      return `Penalty · ${short}`;
    case "goal":
      return `Goal · ${short}`;
    case "half_end":
      return latest.match_clock_ms < 60 * 60_000 ? "Half-time" : "Full time";
    default:
      return null;
  }
}

function PlayerDot({
  player,
  info,
  focused,
}: {
  player: TrackingFrame["players"][number];
  info: MatchInfo;
  focused: boolean;
}) {
  const at = toPitch(player);
  const home = sideOf(info, player.team_id) === "home";
  const number = info.players.get(player.player_id)?.number;
  return (
    <g data-player={player.player_id} data-x={at.x} data-y={at.y}>
      {focused && (
        <circle
          cx={at.x}
          cy={at.y}
          r={3.4}
          className="fill-none stroke-air"
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
      )}
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
        <span className="h-px w-3 bg-ink-2" aria-hidden />
        Pass
      </li>
      <li className="flex items-center gap-1.5">
        <span className="h-0.5 w-3 bg-ink" aria-hidden />
        Shot
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
