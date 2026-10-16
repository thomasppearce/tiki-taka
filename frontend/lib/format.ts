/** Match clock as MM:SS, e.g. 3_792_000 -> "63:12". */
export function formatClock(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

/** A short countdown, e.g. 42_000 -> "0:42". */
export function formatCountdown(ms: number): string {
  const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(totalSeconds / 60)}:${String(totalSeconds % 60).padStart(2, "0")}`;
}

/** The scorebug's clock: "FT" once playback reaches a finished match's final whistle. */
export function scorebugClock(
  clockMs: number,
  card: { status: string; clock_ms: number } | null,
): string {
  return card?.status === "full_time" && clockMs >= card.clock_ms
    ? "FT"
    : formatClock(clockMs);
}
