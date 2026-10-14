"use client";

import { PushPin } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";

import { Crest } from "@/components/Crest";
import { Panel } from "@/components/ui/Panel";
import type {
  LeagueTable,
  MatchCard,
  MatchSignal,
  SideSignal,
} from "@/lib/contracts.generated";

type Zone = "champions" | "continental" | "relegation";

const STAKE_LABEL: Record<Zone, string> = {
  champions: "Title",
  relegation: "Survival",
  continental: "Top four",
};

/**
 * Every match at a glance, like a gallery's multiviewer: the score, how hard each side is
 * pushing, and what a goal would decide. Whoever controls the feed (the producer, or a fan on
 * their own whip-around) cuts or pins from here; everyone else opens the match. `tags` marks the
 * matches that are a fan's own: their club's, or where their fantasy XI is playing.
 */
export function Multiview({
  cards,
  signals,
  table,
  onAirMatchId,
  pendingMatchId,
  pinnedMatchId,
  canCut,
  tags,
  recaps,
  onCut,
  onPin,
}: {
  cards: MatchCard[];
  signals: MatchSignal[];
  table: LeagueTable | null;
  onAirMatchId: string;
  pendingMatchId: string | null;
  pinnedMatchId: string | null;
  canCut: boolean;
  tags?: Map<string, string>;
  /** Each finished match's recap headline. */
  recaps?: Map<string, string>;
  onCut: (matchId: string) => void;
  onPin: (matchId: string | null) => void;
}) {
  const bySignal = new Map(signals.map((s) => [s.match_id, s]));
  return (
    <Panel
      title="All ten matches"
      aside={
        <span className="text-xs text-ink-3">
          {canCut ? "Click a match to cut to it" : "Open any match"}
        </span>
      }
    >
      <ul className="grid grid-cols-1 gap-2 p-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
        {cards.map((card) => (
          <Tile
            key={card.match_id}
            card={card}
            signal={bySignal.get(card.match_id)}
            stakes={stakesOf(table, card.match_id)}
            onAir={card.match_id === onAirMatchId}
            next={card.match_id === pendingMatchId}
            pinned={card.match_id === pinnedMatchId}
            canCut={canCut}
            tag={tags?.get(card.match_id) ?? null}
            recap={recaps?.get(card.match_id) ?? null}
            onCut={onCut}
            onPin={onPin}
          />
        ))}
      </ul>
    </Panel>
  );
}

function Tile({
  card,
  signal,
  stakes,
  onAir,
  next,
  pinned,
  canCut,
  tag,
  recap,
  onCut,
  onPin,
}: {
  card: MatchCard;
  signal: MatchSignal | undefined;
  stakes: Zone[];
  onAir: boolean;
  next: boolean;
  pinned: boolean;
  canCut: boolean;
  tag: string | null;
  recap: string | null;
  onCut: (matchId: string) => void;
  onPin: (matchId: string | null) => void;
}) {
  const minute =
    card.status === "full_time"
      ? "FT"
      : `${Math.floor(card.clock_ms / 60_000) + 1}'`;
  const body = (
    <>
      <div className="flex items-center gap-2 text-xs">
        <span className="font-mono text-ink-3 tabular-nums">{minute}</span>
        {tag && <span className="min-w-0 truncate text-ink-2">{tag}</span>}
        <span className="ml-auto" />
        {onAir ? (
          <span className="rounded-sm bg-air px-1.5 py-0.5 font-medium text-ink-on-fill">
            On air
          </span>
        ) : next ? (
          <span className="rounded-sm border border-air px-1.5 py-px font-medium text-ink">
            Next
          </span>
        ) : null}
      </div>
      <Team
        club={card.home}
        score={card.score_home}
        side={signal?.home}
        tint="bg-home"
      />
      <Team
        club={card.away}
        score={card.score_away}
        side={signal?.away}
        tint="bg-away"
      />
      <p className="mt-1 min-h-4 text-xs text-ink-3">
        {card.status === "full_time" && recap ? (
          <span className="line-clamp-2 text-ink-2">{recap}</span>
        ) : stakes.length ? (
          `At stake: ${stakes.map((z) => STAKE_LABEL[z]).join(", ")}`
        ) : (
          ""
        )}
      </p>
    </>
  );
  const frame = `relative flex w-full flex-col gap-1 rounded-md border p-2.5 text-left transition-[border-color,background-color] duration-(--duration-quick) ease-(--ease-out) focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-air ${
    onAir
      ? "border-air bg-raised"
      : "border-line bg-page hover:border-line-strong hover:bg-raised"
  }`;
  return (
    <li className="relative">
      {canCut ? (
        <button
          type="button"
          className={frame}
          onClick={() => onCut(card.match_id)}
          disabled={onAir}
          aria-label={`Cut to ${card.home.name} v ${card.away.name}`}
        >
          {body}
        </button>
      ) : (
        <Link href={`/match/${card.match_id}`} className={frame}>
          {body}
        </Link>
      )}
      {canCut && (
        <button
          type="button"
          onClick={() => onPin(pinned ? null : card.match_id)}
          aria-pressed={pinned}
          aria-label={
            pinned
              ? "Release the pin"
              : `Pin the feed on ${card.home.short} v ${card.away.short}`
          }
          className={`absolute right-1.5 bottom-1.5 rounded-sm p-1 transition-colors duration-(--duration-quick) focus-visible:outline-2 focus-visible:outline-air ${
            pinned ? "text-air" : "text-ink-3 hover:text-ink"
          }`}
        >
          <PushPin size={14} weight={pinned ? "fill" : "regular"} />
        </button>
      )}
    </li>
  );
}

function Team({
  club,
  score,
  side,
  tint,
}: {
  club: MatchCard["home"];
  score: number;
  side: SideSignal | undefined;
  tint: string;
}) {
  const pressure = Math.round((side?.pressure ?? 0) * 100);
  return (
    <div className="grid grid-cols-[18px_minmax(0,1fr)_auto] items-center gap-x-2">
      <Crest club={club} size={18} />
      <span className="truncate text-sm text-ink">{club.name}</span>
      <span className="font-mono text-sm font-semibold text-ink tabular-nums">
        {score}
      </span>
      <span
        aria-hidden
        className="col-start-2 col-end-4 h-0.5 rounded-full bg-line"
      >
        <span
          className={`block h-full rounded-full ${tint} transition-[width] duration-(--duration-slow) ease-(--ease-smooth-out)`}
          style={{ width: `${pressure}%` }}
        />
      </span>
    </div>
  );
}

/** The zones a goal in this match would change, from the table's stakes. */
function stakesOf(table: LeagueTable | null, matchId: string): Zone[] {
  const zones = new Set<Zone>();
  for (const stake of table?.stakes ?? []) {
    if (stake.match_id !== matchId) continue;
    for (const change of stake.changes)
      for (const zone of [change.from_zone, change.to_zone])
        if (zone) zones.add(zone);
  }
  // A move between first and second is the title, not top four.
  if (zones.has("champions")) zones.delete("continental");
  return (["champions", "relegation", "continental"] as const).filter((z) =>
    zones.has(z),
  );
}
