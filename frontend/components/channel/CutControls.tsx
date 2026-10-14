"use client";

import {
  ClockCounterClockwise,
  FastForward,
  Pause,
  Play,
  PushPinSlash,
} from "@phosphor-icons/react/dist/ssr";
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
  const move = (minute: number | null) => {
    setBusy(true);
    void postJson("/api/clock", minute === null ? {} : { minute })
      .catch(() => undefined)
      .finally(() => setBusy(false));
  };
  return (
    <div className="flex w-full flex-wrap items-center gap-2 border-t border-line pt-2">
      <span className="mr-auto text-xs text-ink-3">
        Match clock (demo, moves everyone watching)
      </span>
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
