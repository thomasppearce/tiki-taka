import { LowerThird } from "@/components/broadcast/LowerThird";
import { Scorebug } from "@/components/broadcast/Scorebug";
import { SyntheticFeed } from "@/components/broadcast/SyntheticFeed";
import { Panel } from "@/components/ui/Panel";
import { MATCH, ON_AIR } from "@/lib/mock";

/** The program output: synthetic camera feed plus whatever graphics are on air. */
export function ProgramMonitor({ clock }: { clock: string }) {
  return (
    <Panel title="Program" aside={<Tally />}>
      <div className="p-3">
        <div className="@container relative isolate aspect-video overflow-hidden rounded-md bg-page">
          <SyntheticFeed />
          <Scorebug score={MATCH.score} clock={clock} />
          <LowerThird
            label={ON_AIR.label}
            headline={ON_AIR.headline}
            split={ON_AIR.split}
            splitLabel={ON_AIR.splitLabel}
          />
        </div>
      </div>
    </Panel>
  );
}

function Tally() {
  return (
    <p className="flex items-center gap-2 text-xs text-ink-2">
      <span className="text-ink-3">Analyst EN feed</span>
      <span className="flex items-center gap-1.5 rounded-md bg-air px-1.5 py-0.5 font-medium text-ink-on-fill">
        On air
      </span>
    </p>
  );
}
