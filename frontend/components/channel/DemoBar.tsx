"use client";

import {
  ClockCounterClockwise,
  FastForward,
  X,
} from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { postJson } from "@/lib/api";
import { useStored } from "@/lib/stored";

const isBoolean = (value: unknown): value is boolean =>
  typeof value === "boolean";

/**
 * Demo controls, apart from the product: jump the one matchday clock to any minute, back to 55',
 * or to the day's last final whistle, so a 40-minute matchday can be explored in a few. No real
 * producer can do this, and it moves everyone watching. It folds away to a small pill (for
 * recording, or once you've seen it).
 */
export function DemoBar() {
  const [hidden, setHidden] = useStored(
    "tikitaka.demo-hidden",
    false,
    isBoolean,
  );
  const [busy, setBusy] = useState(false);
  const [minute, setMinute] = useState("90");
  if (hidden)
    return (
      <button
        type="button"
        onClick={() => setHidden(false)}
        className="justify-self-start rounded-full border border-dashed border-line-strong px-2.5 py-0.5 text-xs text-ink-3 transition-colors duration-(--duration-quick) hover:text-ink focus-visible:outline-2 focus-visible:outline-air"
      >
        Demo controls
      </button>
    );
  const move = (to: number | null) => {
    setBusy(true);
    void postJson("/api/clock", to === null ? {} : { minute: to })
      .catch(() => undefined)
      .finally(() => setBusy(false));
  };
  const typed = Number(minute);
  const valid = Number.isFinite(typed) && typed >= 1 && typed <= 97;
  return (
    <section
      aria-label="Demo controls"
      className="grid gap-2 rounded-lg border border-dashed border-line-strong px-3 py-2"
    >
      <div className="flex items-center gap-3">
        <span className="rounded-sm bg-raised px-1.5 py-0.5 text-xs font-medium text-ink">
          Demo
        </span>
        <p className="mr-auto text-xs text-ink-3">
          Jump the matchday clock to see any moment. A real producer
          can&rsquo;t, and it moves everyone watching.
        </p>
        <button
          type="button"
          onClick={() => setHidden(true)}
          aria-label="Hide the demo controls"
          title="Hide"
          className="rounded-sm p-1 text-ink-3 transition-colors duration-(--duration-quick) hover:text-ink focus-visible:outline-2 focus-visible:outline-air"
        >
          <X size={14} />
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <form
          className="flex items-center gap-1.5"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid) move(typed);
          }}
        >
          <label htmlFor="demo-minute" className="text-xs text-ink-3">
            Minute
          </label>
          <input
            id="demo-minute"
            type="number"
            min={1}
            max={97}
            step="any"
            value={minute}
            onChange={(e) => setMinute(e.target.value)}
            className="h-7 w-16 rounded-md border border-line bg-page px-1.5 text-label text-ink tabular-nums transition-[border-color] duration-150 ease-out hover:border-line-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-air"
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
        <Link
          href="/split"
          className="ml-auto text-xs text-ink-2 underline decoration-line-strong underline-offset-4 hover:text-ink"
        >
          Two fans side by side
        </Link>
      </div>
    </section>
  );
}
