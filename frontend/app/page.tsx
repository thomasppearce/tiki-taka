import { AgentActivity } from "@/components/control-room/AgentActivity";
import { MomentumTimeline } from "@/components/control-room/MomentumTimeline";
import { ProgramMonitor } from "@/components/control-room/ProgramMonitor";
import { ProposalQueue } from "@/components/control-room/ProposalQueue";
import { TacticalPitch } from "@/components/control-room/TacticalPitch";
import { TopBar } from "@/components/control-room/TopBar";
import { formatClock } from "@/lib/format";
import {
  AGENT_STATES,
  AUDIT_LOG,
  MATCH,
  MOMENTUM,
  PROPOSALS,
  RECENT_EVENTS,
  TIMELINE_MARKERS,
} from "@/lib/mock";

/*
 * Three layouts, one tree:
 * - xl (>= 1280px): fixed single-screen control room; the left column fills the viewport height.
 * - lg (1024-1279px): page scrolls; panels stack on the left, the proposal queue stays pinned right.
 * - below lg: one column. The column wrappers become `display: contents` so their panels join the
 *   page grid directly and can be ordered: program, proposals, pitch, momentum, agents.
 */
export default function ControlRoom() {
  const selected = PROPOSALS[0];
  const citedEventIds = new Set(
    selected.claims.flatMap((claim) => claim.evidence_event_ids),
  );
  const clock = formatClock(MATCH.clockMs);

  return (
    <div className="flex min-h-dvh flex-col bg-page xl:h-dvh xl:min-h-[760px]">
      <TopBar clock={clock} activeFeed="feed_analyst_en" />
      <main className="grid flex-1 grid-cols-1 gap-3 p-3 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start xl:min-h-0 xl:grid-cols-[minmax(0,1fr)_360px] xl:items-stretch 2xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="contents lg:grid lg:min-w-0 lg:gap-3 xl:min-h-0 xl:grid-rows-[auto_auto_minmax(0,1fr)]">
          <div className="contents xl:grid xl:min-w-0 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)] xl:gap-3">
            <ProgramMonitor clock={clock} className="order-1 lg:order-none" />
            <TacticalPitch
              events={RECENT_EVENTS}
              citedEventIds={citedEventIds}
              className="order-3 lg:order-none"
            />
          </div>
          <MomentumTimeline
            momentum={MOMENTUM}
            markers={TIMELINE_MARKERS}
            nowMinute={Math.floor(MATCH.clockMs / 60_000)}
            className="order-4 lg:order-none"
          />
          <AgentActivity
            agents={AGENT_STATES}
            log={AUDIT_LOG}
            className="order-5 lg:order-none"
          />
        </div>
        <ProposalQueue
          proposals={PROPOSALS}
          selectedId={selected.proposal_id}
          clockMs={MATCH.clockMs}
          className="order-2 lg:sticky lg:top-3 lg:order-none lg:max-h-[calc(100dvh-1.5rem)] xl:static xl:max-h-none"
        />
      </main>
    </div>
  );
}
