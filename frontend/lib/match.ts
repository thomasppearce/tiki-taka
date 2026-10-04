/**
 * Who is playing: the two clubs and their squads, from the backend's match detail, shared with
 * every view through context. Data views encode the two sides by role (home, away), never by a
 * club's brand color, so components ask for a side rather than a team id.
 */

import { createContext, useContext } from "react";

import type {
  ClubRef,
  MatchDetail,
  PlayerRef,
} from "@/lib/contracts.generated";

export type Side = "home" | "away";

export type MatchInfo = {
  matchId: string;
  leagueName: string;
  home: ClubRef;
  away: ClubRef;
  players: ReadonlyMap<string, PlayerRef>;
};

export function matchInfo(detail: MatchDetail): MatchInfo {
  return {
    matchId: detail.card.match_id,
    leagueName: detail.card.league_name,
    home: detail.card.home,
    away: detail.card.away,
    players: new Map(detail.players.map((p) => [p.player_id, p])),
  };
}

/** Which side a team id belongs to (anything unknown counts as away). */
export function sideOf(info: MatchInfo, teamId: string | null): Side {
  return teamId === info.home.club_id ? "home" : "away";
}

export function club(info: MatchInfo, side: Side): ClubRef {
  return side === "home" ? info.home : info.away;
}

export function surname(name: string): string {
  return name.split(" ").slice(1).join(" ") || name;
}

export const MatchContext = createContext<MatchInfo | null>(null);

/** The match on screen. Only rendered once the match detail has loaded. */
export function useMatch(): MatchInfo {
  const info = useContext(MatchContext);
  if (!info) throw new Error("useMatch outside a loaded match");
  return info;
}
