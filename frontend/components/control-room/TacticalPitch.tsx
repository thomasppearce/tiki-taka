import { EventMarker } from "@/components/pitch/EventMarker";
import { PitchMarkings } from "@/components/pitch/PitchMarkings";
import { Panel } from "@/components/ui/Panel";
import type { MatchEvent } from "@/lib/contracts.generated";
import { CLUBS } from "@/lib/mock";
import { PITCH_VIEWBOX } from "@/lib/pitch";

/**
 * Top-down tactical view of recent events. When a proposal is selected, the events it cites
 * light up and everything else recedes: the evidence view.
 */
export function TacticalPitch({
  events,
  citedEventIds,
  className,
}: {
  events: MatchEvent[];
  citedEventIds: ReadonlySet<string>;
  className?: string;
}) {
  const hasSelection = citedEventIds.size > 0;

  return (
    <Panel title="Tactical view" aside={<Legend />} className={className}>
      <div className="flex flex-1 items-center p-3">
        <svg
          viewBox={PITCH_VIEWBOX}
          className="w-full"
          role="img"
          aria-label={`Pitch with the last ${events.length} events; ${citedEventIds.size} cited by the selected proposal`}
        >
          <PitchMarkings />
          {events.map((event) => {
            const cited = citedEventIds.has(event.event_id);
            return (
              <EventMarker
                key={event.event_id}
                event={event}
                cited={cited}
                dimmed={hasSelection && !cited}
              />
            );
          })}
        </svg>
      </div>
    </Panel>
  );
}

function Legend() {
  return (
    <ul className="flex items-center gap-3 text-xs text-ink-3">
      <li className="flex items-center gap-1.5">
        <span className="size-2 rounded-full bg-home" aria-hidden />
        {CLUBS.t_home.short}
      </li>
      <li className="flex items-center gap-1.5">
        <span className="size-2 rotate-45 bg-away" aria-hidden />
        {CLUBS.t_away.short}
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
