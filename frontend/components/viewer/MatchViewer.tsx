"use client";

import { MotionConfig } from "motion/react";
import { useMemo, useState } from "react";

import { ClubCrest } from "@/components/ClubCrest";
import { MomentumTimeline } from "@/components/control-room/MomentumTimeline";
import { ProgramMonitor } from "@/components/control-room/ProgramMonitor";
import { TacticalPitch } from "@/components/control-room/TacticalPitch";
import { FeedState } from "@/components/match/FeedState";
import { MatchRecapCard } from "@/components/recap/MatchRecapCard";
import { SiteHeader } from "@/components/SiteHeader";
import { FanPreferences } from "@/components/viewer/FanPreferences";
import { KeyMoments } from "@/components/viewer/KeyMoments";
import { SignUpNudge } from "@/components/viewer/SignUpNudge";
import { StatsPanel } from "@/components/viewer/StatsPanel";
import type { MatchDetail } from "@/lib/contracts.generated";
import { onAirGraphic, scoreAt, timelineMarkers } from "@/lib/controlRoom";
import { formatClock, scorebugClock } from "@/lib/format";
import { useEvidence } from "@/lib/live/useEvidence";
import { usePlaybackClock } from "@/lib/live/usePlaybackClock";
import { type LiveMatch, useLiveMatch } from "@/lib/live/useLiveMatch";
import { useMatchRecap } from "@/lib/live/useRecap";
import {
  MatchContext,
  type MatchInfo,
  type Side,
  surname,
  useMatch,
} from "@/lib/match";
import { GUEST_PREFS, useFanPrefs } from "@/lib/role";

const GUEST_MOMENTS = 3;
const HALF_MS = 45 * 60_000;

/**
 * The match for viewers. A fan picks the depth and language of the graphics and can follow a
 * player; a guest gets the casual English feed, the latest few moments, the headline stats, and
 * an invitation to sign up. Both see the same live match and the same approved graphics.
 */
export function MatchViewer({
  matchId,
  role,
}: {
  matchId: string;
  role: "guest" | "fan";
}) {
  const live = useLiveMatch(matchId);
  if (!live.info || !live.baseline || !live.detail)
    return (
      <div className="flex min-h-dvh flex-col bg-page">
        <SiteHeader />
        <FeedState status={live.status} />
      </div>
    );
  return (
    <MatchContext value={live.info}>
      <Viewer
        live={live}
        info={live.info}
        baseline={live.baseline}
        detail={live.detail}
        role={role}
      />
    </MatchContext>
  );
}

function Viewer({
  live,
  info,
  baseline,
  detail,
  role,
}: {
  live: LiveMatch;
  info: MatchInfo;
  baseline: NonNullable<LiveMatch["baseline"]>;
  detail: MatchDetail;
  role: "guest" | "fan";
}) {
  const [stored, setPrefs] = useFanPrefs();
  const prefs = role === "fan" ? stored : GUEST_PREFS;
  const [momentId, setMomentId] = useState<string | null>(null);
  const clockMs = usePlaybackClock(live.source.getClockMs);
  const recap = useMatchRecap(info.matchId);

  const events = useMemo(
    () => live.events.filter((e) => e.match_clock_ms <= clockMs),
    [live.events, clockMs],
  );
  const moments = detail.key_moments
    .filter((m) => m.match_clock_ms <= clockMs)
    .reverse();
  const shown = role === "fan" ? moments : moments.slice(0, GUEST_MOMENTS);
  const selected = moments.find((m) => m.moment_id === momentId) ?? null;
  const citedIds = useMemo(
    () => selected?.evidence_event_ids ?? [],
    [selected],
  );
  const cited = useMemo(() => new Set(citedIds), [citedIds]);
  const older = useEvidence(info.matchId, citedIds, events);
  const pitchEvents = useMemo(() => [...older, ...events], [older, events]);
  const score = scoreAt(info, baseline, live.events, clockMs);
  const minute = Math.floor(clockMs / 60_000);
  const markers = useMemo(
    () => timelineMarkers(info, events, live.history),
    [info, events, live.history],
  );
  const followed = prefs.followPlayerId
    ? info.players.get(prefs.followPlayerId)
    : undefined;
  const view = {
    audience: prefs.audience,
    lang: prefs.lang,
    label: `${prefs.audience === "analyst" ? "Analyst" : "Casual"} ${prefs.lang.toUpperCase()}`,
  };
  const period =
    live.card?.status === "full_time"
      ? "Full time"
      : clockMs < HALF_MS
        ? "1st half"
        : "2nd half";

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-dvh flex-col bg-page">
        <SiteHeader>
          <ScoreLine
            score={score}
            clock={formatClock(clockMs)}
            period={period}
          />
        </SiteHeader>
        <main className="mx-auto grid w-full max-w-[1600px] flex-1 grid-cols-1 gap-3 p-3 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
          <div className="grid min-w-0 gap-3">
            {recap && live.card?.status === "full_time" && (
              <MatchRecapCard recap={recap} />
            )}
            <ProgramMonitor
              clock={scorebugClock(clockMs, live.card)}
              source={live.source}
              score={score}
              view={view}
              onAir={onAirGraphic(live.desk, live.events)}
              focusPlayerId={followed?.player_id ?? null}
            />
            <div className="grid min-w-0 gap-3 xl:grid-cols-2 xl:items-start">
              <TacticalPitch
                events={pitchEvents}
                source={live.source}
                citedEventIds={cited}
                focusPlayerId={followed?.player_id ?? null}
              />
              <MomentumTimeline
                momentum={(live.card?.momentum ?? []).slice(0, minute + 1)}
                markers={markers}
                nowMinute={minute}
              />
            </div>
          </div>
          <aside className="grid min-w-0 gap-3">
            {role === "fan" ? (
              <FanPreferences prefs={stored} onChange={setPrefs} />
            ) : (
              <SignUpNudge />
            )}
            {followed && (
              <p className="rounded-lg border border-line bg-panel px-3 py-2 text-sm text-ink-2">
                Following{" "}
                <span className="text-ink">
                  {followed.number} {surname(followed.name)}
                </span>
                : ringed on the camera and the tactical view.
              </p>
            )}
            <KeyMoments
              moments={shown}
              selectedId={selected?.moment_id ?? null}
              onSelect={setMomentId}
              receipts={role === "fan"}
              hiddenCount={moments.length - shown.length}
            />
            <StatsPanel
              home={detail.home_stats}
              away={detail.away_stats}
              full={role === "fan"}
            />
          </aside>
        </main>
      </div>
    </MotionConfig>
  );
}

function ScoreLine({
  score,
  clock,
  period,
}: {
  score: Record<Side, number>;
  clock: string;
  period: string;
}) {
  const { home, away } = useMatch();
  return (
    <div className="flex items-center gap-3 text-sm whitespace-nowrap">
      <span className="hidden text-ink-2 sm:inline">{home.short}</span>
      <ClubCrest side="home" />
      <span className="flex items-center gap-1 font-mono text-xl leading-none font-semibold text-ink tabular-nums">
        <span className="sr-only">Score</span>
        {score.home}
        <span className="text-ink-3">-</span>
        {score.away}
      </span>
      <ClubCrest side="away" />
      <span className="hidden text-ink-2 sm:inline">{away.short}</span>
      <span className="ml-2 font-mono text-ink tabular-nums">{clock}</span>
      <span className="hidden text-xs text-ink-3 md:inline">{period}</span>
    </div>
  );
}
