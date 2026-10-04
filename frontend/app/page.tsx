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

// Design pass: the control room on mock data. The live stream and agents replace the mocks.
export default function ControlRoom() {
  const selected = PROPOSALS[0];
  const citedEventIds = new Set(
    selected.claims.flatMap((claim) => claim.evidence_event_ids),
  );
  const clock = formatClock(MATCH.clockMs);

  return (
    <div className="flex h-dvh min-h-[720px] flex-col bg-page">
      <TopBar clock={clock} activeFeed="feed_analyst_en" />
      <main className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_400px] gap-3 p-3">
        <div className="grid min-h-0 grid-rows-[auto_auto_minmax(0,1fr)] gap-3">
          <div className="grid grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)] gap-3">
            <ProgramMonitor clock={clock} />
            <TacticalPitch
              events={RECENT_EVENTS}
              citedEventIds={citedEventIds}
            />
          </div>
          <MomentumTimeline
            momentum={MOMENTUM}
            markers={TIMELINE_MARKERS}
            nowMinute={Math.floor(MATCH.clockMs / 60_000)}
          />
          <AgentActivity agents={AGENT_STATES} log={AUDIT_LOG} />
        </div>
        <ProposalQueue
          proposals={PROPOSALS}
          selectedId={selected.proposal_id}
          clockMs={MATCH.clockMs}
        />
      </main>
    </div>
  );
}
