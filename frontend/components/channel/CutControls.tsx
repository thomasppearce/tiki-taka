"use client";

import {
  ClockCounterClockwise,
  FastForward,
  Pause,
  Play,
  PushPinSlash,
} from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { postJson } from "@/lib/api";
import type { Channel } from "@/lib/contracts.generated";
import type { ChannelControls } from "@/lib/live/useChannel";
import { useCountdown } from "@/lib/live/useCountdown";

/**
 * The producer's hand on the channel. The Director cuts on its own after a short countdown; the
 * producer can take the cut now, hold automatic cuts, or release a pin.
 */
export function CutControls({
  channel,
  controls,
  fixtureOf,
  serverClockMs,
}: {
  channel: Channel;
  controls: ChannelControls;
  fixtureOf: (matchId: string) => string;
  serverClockMs: () => number;
}) {
  const { pending, held, pinned_match_id: pinned } = channel;
  return (
    <section
      aria-label="Cut controls"
      className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-line bg-panel px-3 py-2"
    >
      <p className="text-sm text-ink-2">
        {pinned ? (
          <>
            Pinned on <span className="text-ink">{fixtureOf(pinned)}</span>: the
            Director won’t cut away.
          </>
        ) : held ? (
          "Automatic cuts held. The Director keeps watching but won’t cut."
        ) : pending ? (
          <Pending
            fixture={fixtureOf(pending.match_id)}
            why={pending.package.why}
            takeAtMs={pending.take_at_ms}
            serverClockMs={serverClockMs}
          />
        ) : (
          "The Director is watching all ten matches."
        )}
      </p>
      <div className="ml-auto flex gap-2">
        {pending && !held && !pinned && (
          <Button variant="primary" onClick={() => void controls.take()}>
            Take now
          </Button>
        )}
        {pinned ? (
          <Button onClick={() => void controls.pin(null)}>
            <PushPinSlash size={14} /> Release pin
          </Button>
        ) : (
          <Button onClick={() => void controls.hold(!held)} aria-pressed={held}>
            {held ? <Play size={14} /> : <Pause size={14} />}
            {held ? "Resume cuts" : "Hold cuts"}
          </Button>
        )}
      </div>
      <DemoClock />
    </section>
  );
}

/**
 * Demo controls for the one matchday clock: skip to the day's last final whistle (the recaps),
 * or back to 55'. Everyone watching moves with it.
 */
function DemoClock() {
  const [busy, setBusy] = useState(false);
  const [minute, setMinute] = useState("90");
  const move = (to: number | null) => {
    setBusy(true);
    void postJson("/api/clock", to === null ? {} : { minute: to })
      .catch(() => undefined)
      .finally(() => setBusy(false));
  };
  const typed = Number(minute);
  const valid = Number.isFinite(typed) && typed >= 1 && typed <= 97;
  return (
    <div className="flex w-full flex-wrap items-center gap-2 border-t border-line pt-2">
      <span className="mr-auto text-xs text-ink-3">
        Match clock (demo, moves everyone watching) &middot;{" "}
        <Link
          href="/split"
          className="text-ink-2 underline decoration-line-strong underline-offset-4 hover:text-ink"
        >
          two fans side by side
        </Link>
      </span>
      <form
        className="flex items-center gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) move(typed);
        }}
      >
        <label htmlFor="demo-minute" className="sr-only">
          Minute to jump to
        </label>
        <input
          id="demo-minute"
          type="number"
          min={1}
          max={97}
          value={minute}
          onChange={(e) => setMinute(e.target.value)}
          className="h-7 w-14 rounded-md border border-line bg-page px-1.5 text-label text-ink tabular-nums transition-[border-color] duration-150 ease-out hover:border-line-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-air"
        />
        <Button type="submit" disabled={busy || !valid}>
          Jump
        </Button>
      </form>
      <Button onClick={() => move(55)} disabled={busy}>
        <ClockCounterClockwise size={14} /> Back to 55&prime;
      </Button>
      <Button onClick={() => move(null)} disabled={busy}>
        <FastForward size={14} /> Skip to the final whistle
      </Button>
    </div>
  );
}

function Pending({
  fixture,
  why,
  takeAtMs,
  serverClockMs,
}: {
  fixture: string;
  why: string;
  takeAtMs: number;
  serverClockMs: () => number;
}) {
  const seconds = useCountdown(takeAtMs, serverClockMs);
  return (
    <>
      Cutting to <span className="text-ink">{fixture}</span> in{" "}
      <span className="font-mono text-ink tabular-nums">{seconds}s</span>: {why}
    </>
  );
}
