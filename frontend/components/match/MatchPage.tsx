"use client";

import { ControlRoom } from "@/components/ControlRoom";
import { MatchViewer } from "@/components/viewer/MatchViewer";
import { useRole } from "@/lib/role";

/** One match, seen as the current role: the control room for producers, the viewer otherwise. */
export function MatchPage({ matchId }: { matchId: string }) {
  const [role] = useRole();
  return role === "producer" ? (
    <ControlRoom matchId={matchId} />
  ) : (
    <MatchViewer matchId={matchId} role={role} />
  );
}
