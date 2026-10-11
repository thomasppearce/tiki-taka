"use client";

import { CaretRight, PencilSimple } from "@phosphor-icons/react/dist/ssr";

import { Crest } from "@/components/Crest";
import { Button } from "@/components/ui/Button";
import { Panel } from "@/components/ui/Panel";
import type { ClubRef, FantasyPlayer, Lens } from "@/lib/contracts.generated";
import { XI_SHAPE, type XiRole } from "@/lib/whip";

/**
 * A fan's fantasy XI on their own whip-around: live points as it stands, by line, and for each
 * player the lines that earned them, each backed by match events.
 */
export function FantasyXi({
  lens,
  clubs,
  onAirMatchId,
  onEdit,
}: {
  lens: Lens;
  clubs: Map<string, ClubRef>;
  onAirMatchId: string;
  onEdit: () => void;
}) {
  return (
    <Panel
      title="Your XI"
      aside={
        <span className="flex items-center gap-3">
          <span className="text-sm text-ink-2">
            <span className="font-mono text-base font-semibold text-ink tabular-nums">
              {lens.points}
            </span>{" "}
            pts
          </span>
          <Button onClick={onEdit} aria-label="Edit your XI">
            <PencilSimple size={14} /> Edit
          </Button>
        </span>
      }
    >
      <div className="px-3 py-2">
        {(Object.keys(XI_SHAPE) as XiRole[]).map((role) => {
          const line = lens.xi.filter((p) => p.role === role);
          if (!line.length) return null;
          return (
            <section key={role} className="py-1">
              <h3 className="py-1 text-xs text-ink-3">
                {XI_SHAPE[role].label}
              </h3>
              <ul>
                {line.map((p) => (
                  <Player
                    key={p.player_id}
                    player={p}
                    club={clubs.get(p.club_id)}
                    onAir={p.match_id === onAirMatchId}
                  />
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </Panel>
  );
}

function Player({
  player,
  club,
  onAir,
}: {
  player: FantasyPlayer;
  club: ClubRef | undefined;
  onAir: boolean;
}) {
  const receipts = new Set(player.items.flatMap((i) => i.event_ids)).size;
  const surname = player.name.split(" ").slice(1).join(" ") || player.name;
  return (
    <li>
      <details className="group">
        <summary className="grid cursor-pointer list-none grid-cols-[12px_18px_minmax(0,1fr)_auto] items-center gap-x-2 rounded-sm py-1 text-sm transition-colors duration-(--duration-quick) hover:bg-raised focus-visible:outline-2 focus-visible:outline-air [&::-webkit-details-marker]:hidden">
          <CaretRight
            size={12}
            className="text-ink-3 transition-transform duration-(--duration-quick) ease-(--ease-out) group-open:rotate-90"
          />
          {club ? <Crest club={club} size={18} /> : <span />}
          <span className="flex min-w-0 items-center gap-2">
            <span className={`truncate ${onAir ? "text-ink" : "text-ink-2"}`}>
              {surname}
            </span>
            {onAir && (
              <span className="shrink-0 rounded-sm bg-air px-1 text-[11px] font-medium text-ink-on-fill">
                On air
              </span>
            )}
            {!player.on_pitch && player.items.length > 0 && (
              <span className="shrink-0 text-xs text-ink-3">off</span>
            )}
          </span>
          <span className="font-mono font-semibold text-ink tabular-nums">
            {player.points}
          </span>
        </summary>
        <div className="pb-2 pl-[3.25rem] text-xs text-ink-2">
          {player.items.length ? (
            <ul className="grid gap-0.5">
              {player.items.map((item, i) => (
                <li key={`${item.label}-${i}`} className="flex justify-between">
                  <span>{item.label}</span>
                  <span className="font-mono tabular-nums">
                    {item.points > 0 ? `+${item.points}` : item.points}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-ink-3">Not on the pitch yet.</p>
          )}
          {receipts > 0 && (
            <p className="mt-1 text-ink-3">
              From {receipts} match {receipts === 1 ? "event" : "events"}
            </p>
          )}
        </div>
      </details>
    </li>
  );
}
