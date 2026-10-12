import { API_URL } from "@/lib/api";

/**
 * Before the data has loaded: connecting, or the backend can't be reached. The deployed backend
 * scales to zero when nobody is watching, so the first visit after a quiet spell waits a few
 * seconds while it wakes; the page says so, and keeps trying on its own.
 */
export function FeedState({
  status,
  what = "the match feed",
}: {
  status: "connecting" | "live" | "reconnecting" | "offline";
  what?: string;
}) {
  const offline = status === "offline";
  const dev = process.env.NODE_ENV === "development";
  const title = offline ? `Can't reach ${what} yet` : `Tuning in to ${what}`;
  return (
    <main className="grid flex-1 place-items-center bg-page p-6">
      <div className="max-w-md text-center" role="status">
        <p
          className={`text-sm font-semibold text-ink ${offline ? "" : "t-think-text"}`}
          data-text={title}
        >
          {title}
        </p>
        <p className="mt-2 text-sm text-ink-2">
          {offline && dev ? (
            <>
              Nothing is answering at{" "}
              <code className="font-mono text-ink">{API_URL}</code>. Start the
              backend with{" "}
              <code className="font-mono text-ink">make dev-backend</code>; this
              page reconnects on its own.
            </>
          ) : offline ? (
            "The studio is still waking up. This page keeps trying on its own."
          ) : (
            "The studio wakes up when someone tunes in, so the first visit takes a few seconds."
          )}
        </p>
      </div>
    </main>
  );
}
