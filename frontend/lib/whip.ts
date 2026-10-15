"use client";

import { useStored } from "@/lib/stored";

/**
 * A signed-in fan's own whip-around: the main channel, cut by what matters to their club, or cut
 * by their fantasy XI. Guests get the main channel. The server keeps one Director per club or XI
 * (the "lens"); this is just what the fan picked, remembered on their device.
 */
export type WhipMode = "channel" | "club" | "fantasy";

export type WhipPrefs = {
  mode: WhipMode;
  clubId: string | null;
  xi: string[];
};

export const DEFAULT_WHIP: WhipPrefs = {
  mode: "channel",
  clubId: null,
  xi: [],
};

const isWhip = (value: unknown): value is WhipPrefs => {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    (v.mode === "channel" || v.mode === "club" || v.mode === "fantasy") &&
    (v.clubId === null || typeof v.clubId === "string") &&
    Array.isArray(v.xi) &&
    v.xi.every((p) => typeof p === "string")
  );
};

export function useWhip(): [WhipPrefs, (prefs: WhipPrefs) => void] {
  return useStored<WhipPrefs>("tikitaka.whip", DEFAULT_WHIP, isWhip);
}

/** The server's lens for these prefs, or null for the main channel (or an unfinished pick). */
export function lensOf(prefs: WhipPrefs): string | null {
  if (prefs.mode === "club" && prefs.clubId) return `club:${prefs.clubId}`;
  if (prefs.mode === "fantasy" && prefs.xi.length === XI_SIZE)
    return `xi:${[...prefs.xi].sort().join(",")}`;
  return null;
}

/** The XI rules, as the server checks them (app/state/fantasy.py), so the picker can guide. */
export const XI_SIZE = 11;
export const PER_CLUB = 3;
export const XI_SHAPE = {
  gk: { min: 1, max: 1, label: "Goalkeeper", plural: "goalkeeper" },
  def: { min: 3, max: 5, label: "Defenders", plural: "defenders" },
  mid: { min: 2, max: 5, label: "Midfielders", plural: "midfielders" },
  fwd: { min: 1, max: 3, label: "Forwards", plural: "forwards" },
} as const;
export type XiRole = keyof typeof XI_SHAPE;
