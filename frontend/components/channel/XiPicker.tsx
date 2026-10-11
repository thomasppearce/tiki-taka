"use client";

import {
  MagnifyingGlass,
  Minus,
  Plus,
  Sparkle,
  X,
} from "@phosphor-icons/react/dist/ssr";
import { useEffect, useMemo, useRef, useState } from "react";

import { Crest } from "@/components/Crest";
import { Button } from "@/components/ui/Button";
import { Segmented } from "@/components/ui/Segmented";
import type { ClubRef, PlayerRef, Squads } from "@/lib/contracts.generated";
import { PER_CLUB, XI_SHAPE, XI_SIZE, type XiRole } from "@/lib/whip";

const ROLES = Object.keys(XI_SHAPE) as XiRole[];
const ROLE_SHORT: Record<XiRole, string> = {
  gk: "GK",
  def: "DEF",
  mid: "MID",
  fwd: "FWD",
};

/**
 * Pick a fantasy XI from the league's players: one goalkeeper, three to five defenders, two to
 * five midfielders, one to three forwards, at most three from a club. The rules are checked as
 * you pick (and again by the server); the team of the season is one click away.
 */
export function XiPicker({
  open,
  squads,
  clubs,
  initial,
  onSave,
  onClose,
}: {
  open: boolean;
  squads: Squads;
  clubs: Map<string, ClubRef>;
  initial: string[];
  onSave: (xi: string[]) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [xi, setXi] = useState<string[]>(initial);
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<XiRole | "all">("all");
  const [clubId, setClubId] = useState("");

  useEffect(() => {
    const d = dialog.current;
    if (!d) return;
    if (open && !d.open) {
      setXi(initial.length ? initial : squads.suggested_xi);
      d.showModal();
    } else if (!open && d.open) d.close();
  }, [open, initial, squads.suggested_xi]);

  const byId = useMemo(
    () => new Map(squads.players.map((p) => [p.player_id, p])),
    [squads.players],
  );
  const picked = xi.flatMap((id) => byId.get(id) ?? []);
  const problems = check(picked);
  const shown = squads.players.filter(
    (p) =>
      (role === "all" || p.role === role) &&
      (!clubId || p.club_id === clubId) &&
      (!query || p.name.toLowerCase().includes(query.trim().toLowerCase())),
  );
  const toggle = (id: string) =>
    setXi((now) =>
      now.includes(id) ? now.filter((p) => p !== id) : [...now, id],
    );

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      aria-labelledby="xi-picker-title"
      className="m-auto h-[min(44rem,92dvh)] w-[min(60rem,calc(100vw-2rem))] overflow-hidden rounded-lg border border-line-strong bg-panel p-0 text-ink shadow-[0_24px_48px_-12px_rgb(0_0_0/0.6)] backdrop:bg-page/70"
    >
      <div className="flex h-full flex-col">
        <header className="flex items-center gap-3 border-b border-line px-4 py-3">
          <h2 id="xi-picker-title" className="text-base font-medium">
            Your fantasy XI
          </h2>
          <span className="font-mono text-sm text-ink-3 tabular-nums">
            {picked.length}/{XI_SIZE}
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="ml-auto rounded-sm p-1 text-ink-3 transition-colors duration-(--duration-quick) hover:text-ink focus-visible:outline-2 focus-visible:outline-air"
          >
            <X size={18} />
          </button>
        </header>

        <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
          {/* The XI, by line */}
          <section
            aria-label="Picked"
            className="min-h-0 overflow-y-auto border-b border-line p-4 md:border-r md:border-b-0"
          >
            {ROLES.map((r) => {
              const inRole = picked.filter((p) => p.role === r);
              const { min, max, label } = XI_SHAPE[r];
              return (
                <div key={r} className="mb-4 last:mb-0">
                  <h3 className="mb-1.5 flex items-baseline justify-between text-xs text-ink-3">
                    <span>{label}</span>
                    <span className="font-mono tabular-nums">
                      {inRole.length} of {min === max ? min : `${min}-${max}`}
                    </span>
                  </h3>
                  {inRole.length ? (
                    <ul className="grid gap-1">
                      {inRole.map((p) => (
                        <PlayerRow
                          key={p.player_id}
                          player={p}
                          club={clubs.get(p.club_id)}
                          picked
                          onToggle={toggle}
                        />
                      ))}
                    </ul>
                  ) : (
                    <p className="rounded-md border border-dashed border-line px-2.5 py-2 text-sm text-ink-3">
                      Nobody yet
                    </p>
                  )}
                </div>
              );
            })}
          </section>

          {/* Everyone else */}
          <section aria-label="Players" className="flex min-h-0 flex-col">
            <div className="grid gap-2 border-b border-line p-3">
              <label className="relative block">
                <span className="sr-only">Search players</span>
                <MagnifyingGlass
                  size={14}
                  className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-ink-3"
                />
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search by name"
                  className="h-8 w-full rounded-md border border-line bg-page pr-2 pl-8 text-sm text-ink transition-[border-color] duration-(--duration-quick) placeholder:text-ink-3 hover:border-line-strong focus-visible:border-air focus-visible:outline-none"
                />
              </label>
              <div className="flex flex-wrap items-center gap-2">
                <Segmented
                  label="Position"
                  size="sm"
                  value={role}
                  onChange={setRole}
                  options={[
                    { value: "all", label: "All" },
                    ...ROLES.map((r) => ({ value: r, label: ROLE_SHORT[r] })),
                  ]}
                />
                <label className="min-w-0 flex-1">
                  <span className="sr-only">Club</span>
                  <select
                    value={clubId}
                    onChange={(e) => setClubId(e.target.value)}
                    className="h-7 w-full rounded-md border border-line bg-page px-2 text-label text-ink-2 transition-[border-color] duration-(--duration-quick) hover:border-line-strong focus-visible:border-air focus-visible:outline-none"
                  >
                    <option value="">Every club</option>
                    {[...clubs.values()]
                      .sort((a, b) => a.name.localeCompare(b.name))
                      .map((c) => (
                        <option key={c.club_id} value={c.club_id}>
                          {c.name}
                        </option>
                      ))}
                  </select>
                </label>
              </div>
            </div>
            <ul className="grid min-h-0 flex-1 auto-rows-min gap-1 overflow-y-auto p-3">
              {shown.length ? (
                shown.map((p) => (
                  <PlayerRow
                    key={p.player_id}
                    player={p}
                    club={clubs.get(p.club_id)}
                    picked={xi.includes(p.player_id)}
                    blocked={
                      xi.includes(p.player_id) ? null : blockedBy(p, picked)
                    }
                    onToggle={toggle}
                  />
                ))
              ) : (
                <li className="p-2 text-sm text-ink-3">
                  No players match. Try another name or club.
                </li>
              )}
            </ul>
          </section>
        </div>

        <footer className="grid gap-3 border-t border-line px-4 py-3">
          <details className="text-sm text-ink-2">
            <summary className="w-fit cursor-pointer text-xs text-ink-3 transition-colors duration-(--duration-quick) hover:text-ink">
              How points work
            </summary>
            <ul className="mt-2 grid list-disc gap-1 pl-5 text-xs text-ink-2">
              {squads.rules.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>
          </details>
          <div className="flex flex-wrap items-center gap-2">
            <p
              role="status"
              className={`mr-auto text-sm ${problems.length ? "text-ink-3" : "text-ink-2"}`}
            >
              {problems.length
                ? problems[0]
                : "Ready: eleven players, all rules met."}
            </p>
            <Button onClick={() => setXi(squads.suggested_xi)}>
              <Sparkle size={14} /> Team of the season
            </Button>
            <Button
              variant="primary"
              disabled={problems.length > 0}
              onClick={() => onSave(xi)}
            >
              Follow this XI
            </Button>
          </div>
        </footer>
      </div>
    </dialog>
  );
}

function PlayerRow({
  player,
  club,
  picked,
  blocked = null,
  onToggle,
}: {
  player: PlayerRef;
  club: ClubRef | undefined;
  picked: boolean;
  blocked?: string | null;
  onToggle: (id: string) => void;
}) {
  const action = picked ? "Remove" : "Add";
  return (
    <li>
      <button
        type="button"
        onClick={() => onToggle(player.player_id)}
        disabled={blocked !== null}
        title={blocked ?? undefined}
        aria-label={`${action} ${player.name}${blocked ? `: ${blocked}` : ""}`}
        className={`group grid w-full grid-cols-[18px_minmax(0,1fr)_auto_auto] items-center gap-x-2 rounded-md border px-2.5 py-1.5 text-left text-sm transition-[background-color,border-color] duration-(--duration-quick) ease-(--ease-out) focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-air disabled:cursor-not-allowed disabled:opacity-40 ${
          picked
            ? "border-line-strong bg-raised"
            : "border-transparent hover:border-line hover:bg-raised"
        }`}
      >
        {club ? <Crest club={club} size={18} /> : <span />}
        <span className="truncate text-ink">
          {player.name}
          <span className="ml-2 text-xs text-ink-3">{club?.short}</span>
        </span>
        <span className="font-mono text-xs text-ink-3">
          {ROLE_SHORT[player.role]}
        </span>
        <span className="text-ink-3 transition-colors duration-(--duration-quick) group-hover:text-ink">
          {picked ? <Minus size={14} /> : <Plus size={14} />}
        </span>
      </button>
    </li>
  );
}

/** Why a player can't join this XI right now, or null if they can. */
function blockedBy(player: PlayerRef, picked: PlayerRef[]): string | null {
  if (picked.length >= XI_SIZE) return "Your XI is full";
  const { max, plural } = XI_SHAPE[player.role];
  if (picked.filter((p) => p.role === player.role).length >= max)
    return `No more than ${max} ${plural}`;
  if (picked.filter((p) => p.club_id === player.club_id).length >= PER_CLUB)
    return `No more than ${PER_CLUB} from one club`;
  return null;
}

/** What still stops this XI, first things first (the server checks the same rules). */
function check(picked: PlayerRef[]): string[] {
  const problems: string[] = [];
  if (picked.length < XI_SIZE)
    problems.push(`Pick ${XI_SIZE - picked.length} more.`);
  for (const r of ROLES) {
    const n = picked.filter((p) => p.role === r).length;
    const { min, plural } = XI_SHAPE[r];
    if (n < min) problems.push(`You need ${min - n} more ${plural}.`);
  }
  return problems;
}
