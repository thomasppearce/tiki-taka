"use client";

import type { Audience, Lang } from "@/lib/i18n";
import { useStored } from "@/lib/stored";

/**
 * Who is watching. Accounts are simulated for the demo: anyone can switch role, and "signing in"
 * just switches to Fan. A guest gets the match with lighter data and a nudge to sign up; a fan
 * chooses their feed and follows a player; a producer gets the control room.
 */
export type Role = "guest" | "fan" | "producer";

export const ROLES: Record<Role, { label: string; description: string }> = {
  guest: { label: "Guest", description: "Watch without an account" },
  fan: { label: "Fan", description: "Signed in: your feed, your player" },
  producer: { label: "Producer", description: "Approve what goes on air" },
};

const isRole = (value: unknown): value is Role =>
  value === "guest" || value === "fan" || value === "producer";

export function useRole(): [Role, (role: Role) => void] {
  return useStored<Role>("tikitaka.role", "guest", isRole);
}

/** A signed-in fan's feed: depth and language of the graphics, and a player to follow. */
export type FanPrefs = {
  audience: Audience;
  lang: Lang;
  followPlayerId: string | null;
};

export const GUEST_PREFS: FanPrefs = {
  audience: "casual",
  lang: "en",
  followPlayerId: null,
};

const isPrefs = (value: unknown): value is FanPrefs => {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    (v.audience === "analyst" || v.audience === "casual") &&
    (v.lang === "en" || v.lang === "es") &&
    (v.followPlayerId === null || typeof v.followPlayerId === "string")
  );
};

export function useFanPrefs(): [FanPrefs, (prefs: FanPrefs) => void] {
  return useStored<FanPrefs>("tikitaka.fan", GUEST_PREFS, isPrefs);
}
