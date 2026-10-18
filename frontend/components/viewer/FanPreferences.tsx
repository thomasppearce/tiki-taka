"use client";

import type { ReactNode } from "react";

import { Panel } from "@/components/ui/Panel";
import { Segmented } from "@/components/ui/Segmented";
import { type Side, club, useMatch } from "@/lib/match";
import type { FanPrefs } from "@/lib/role";

/** A signed-in fan's feed: how deep the graphics go, which language, and a player to follow. */
export function FanPreferences({
  prefs,
  onChange,
  className = "",
}: {
  prefs: FanPrefs;
  onChange: (prefs: FanPrefs) => void;
  className?: string;
}) {
  const info = useMatch();
  const squads = (["home", "away"] as Side[]).map((side) => ({
    club: club(info, side),
    players: [...info.players.values()]
      .filter((p) => p.club_id === club(info, side).club_id)
      .sort((a, b) => a.number - b.number),
  }));

  return (
    <Panel title="Your feed" className={className}>
      <div className="flex flex-col gap-3 p-3">
        <Field label="Graphics">
          <Segmented
            label="Graphics"
            size="sm"
            value={prefs.audience}
            onChange={(audience) => onChange({ ...prefs, audience })}
            options={[
              { value: "casual", label: "Casual" },
              { value: "analyst", label: "Analyst" },
            ]}
          />
        </Field>
        <Field label="Language">
          <Segmented
            label="Language"
            size="sm"
            value={prefs.lang}
            onChange={(lang) => onChange({ ...prefs, lang })}
            options={[
              { value: "en", label: "English" },
              { value: "es", label: "Español" },
            ]}
          />
        </Field>
        <p className="text-xs text-ink-3">
          The match&rsquo;s on-air graphics: the Localizer agent writes each one
          four ways, plain or in depth, in English or Spanish. These pick yours.
        </p>
        <label className="flex items-center justify-between gap-3 text-sm text-ink-2">
          Follow a player
          <select
            value={prefs.followPlayerId ?? ""}
            onChange={(e) =>
              onChange({ ...prefs, followPlayerId: e.target.value || null })
            }
            className="h-7 max-w-[60%] min-w-0 rounded-md border border-line bg-raised px-2 text-label text-ink focus-visible:outline-2 focus-visible:outline-air"
          >
            <option value="">Nobody</option>
            {squads.map(({ club, players }) => (
              <optgroup key={club.club_id} label={club.name}>
                {players.map((p) => (
                  <option key={p.player_id} value={p.player_id}>
                    {p.number} {p.name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
      </div>
    </Panel>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-ink-2">{label}</span>
      {children}
    </div>
  );
}
