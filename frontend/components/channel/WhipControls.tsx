"use client";

import { PencilSimple, UsersThree } from "@phosphor-icons/react/dist/ssr";

import { Button } from "@/components/ui/Button";
import { Segmented } from "@/components/ui/Segmented";
import type { ClubRef, Lens } from "@/lib/contracts.generated";
import { useRole } from "@/lib/role";
import { type WhipMode, type WhipPrefs, XI_SIZE } from "@/lib/whip";

const MODES: { value: WhipMode; label: string }[] = [
  { value: "channel", label: "Main channel" },
  { value: "club", label: "My club" },
  { value: "fantasy", label: "My XI" },
];

/**
 * A signed-in fan's whip-around: the main channel, or their own, cut by what matters to their
 * club or by their fantasy XI. Their own feed is theirs to steer: click a match to cut to it.
 */
export function WhipControls({
  whip,
  setWhip,
  clubs,
  lens,
  onEditXi,
}: {
  whip: WhipPrefs;
  setWhip: (prefs: WhipPrefs) => void;
  clubs: Map<string, ClubRef>;
  lens: Lens | null;
  onEditXi: () => void;
}) {
  const club = whip.clubId ? clubs.get(whip.clubId) : undefined;
  const hasXi = whip.xi.length === XI_SIZE;
  const choose = (mode: WhipMode) => {
    setWhip({ ...whip, mode });
    if (mode === "fantasy" && !hasXi) onEditXi();
  };
  return (
    <section
      aria-label="Your whip-around"
      className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-line bg-panel px-3 py-2"
    >
      <Segmented
        label="Whose whip-around"
        value={whip.mode}
        onChange={choose}
        options={MODES}
      />
      {whip.mode === "club" && (
        <label className="flex items-center gap-2 text-sm text-ink-2">
          <span className="sr-only">Your club</span>
          <select
            value={whip.clubId ?? ""}
            onChange={(e) =>
              setWhip({ ...whip, clubId: e.target.value || null })
            }
            className="h-7 rounded-md border border-line bg-page px-2 text-label text-ink transition-[border-color] duration-(--duration-quick) hover:border-line-strong focus-visible:border-air focus-visible:outline-none"
          >
            <option value="">Pick your club</option>
            {[...clubs.values()]
              .sort((a, b) => a.name.localeCompare(b.name))
              .map((c) => (
                <option key={c.club_id} value={c.club_id}>
                  {c.name}
                </option>
              ))}
          </select>
        </label>
      )}
      {whip.mode === "fantasy" &&
        (hasXi ? (
          <Button onClick={onEditXi}>
            <PencilSimple size={14} /> Edit XI
          </Button>
        ) : (
          <Button variant="primary" onClick={onEditXi}>
            <UsersThree size={14} /> Pick your XI
          </Button>
        ))}
      <p className="text-sm text-ink-3 sm:ml-auto">
        {whip.mode === "channel"
          ? "The Director cuts for the whole table."
          : whip.mode === "club"
            ? club
              ? `Cutting for ${club.name}: their match, and every goal that moves them.`
              : "Pick your club, and the feed cuts to what matters to it."
            : hasXi && lens?.kind === "fantasy"
              ? `Cutting for your XI: ${lens.points} pts so far. Click a match to cut.`
              : "Pick eleven players, and the feed follows their big moments."}
      </p>
    </section>
  );
}

/** For guests: the main channel, and what signing in adds to it. */
export function WhipNudge() {
  const [, setRole] = useRole();
  return (
    <section
      aria-label="Your own whip-around"
      className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-line bg-panel px-3 py-2"
    >
      <p className="text-sm text-ink-2">
        You&rsquo;re watching the main channel.{" "}
        <span className="text-ink-3">
          Sign in to make it yours: cut by what matters to your club, or follow
          your fantasy XI.
        </span>
      </p>
      <Button
        variant="primary"
        className="sm:ml-auto"
        onClick={() => setRole("fan")}
      >
        Sign in free
      </Button>
    </section>
  );
}
