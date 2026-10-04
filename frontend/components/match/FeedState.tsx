import { API_URL } from "@/lib/api";

/** Before the data has loaded: connecting, or the backend can't be reached. */
export function FeedState({
  status,
  what = "the match feed",
}: {
  status: "connecting" | "live" | "reconnecting" | "offline";
  what?: string;
}) {
  const offline = status === "offline";
  return (
    <main className="grid flex-1 place-items-center bg-page p-6">
      <div className="max-w-md text-center">
        <p className="text-sm font-semibold text-ink">
          {offline ? `Can't reach ${what}` : `Connecting to ${what}`}
        </p>
        <p className="mt-2 text-sm text-ink-2">
          {offline ? (
            <>
              Nothing is answering at{" "}
              <code className="font-mono text-ink">{API_URL}</code>. Start the
              backend with{" "}
              <code className="font-mono text-ink">make dev-backend</code>; this
              page reconnects on its own.
            </>
          ) : (
            "Loading the clubs, the squads, and the latest play."
          )}
        </p>
      </div>
    </main>
  );
}
