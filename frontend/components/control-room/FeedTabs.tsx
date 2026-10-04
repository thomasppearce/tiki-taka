"use client";

import { useEffect, useLayoutEffect, useRef } from "react";

import { FEEDS, type FeedId } from "@/lib/controlRoom";

/**
 * Output-feed switcher with the transitions.dev sliding pill. The pill is measured from the
 * active tab; on first paint and resize it snaps without a transition.
 */
export function FeedTabs({
  active,
  onChange,
}: {
  active: FeedId;
  onChange: (feed: FeedId) => void;
}) {
  const pill = useRef<HTMLSpanElement>(null);
  const tabs = useRef<Partial<Record<FeedId, HTMLButtonElement | null>>>({});
  const placed = useRef(false);

  useLayoutEffect(() => {
    const animate = placed.current;
    place(pill.current, tabs.current[active], animate);
    placed.current = true;
  }, [active]);

  useEffect(() => {
    const onResize = () => place(pill.current, tabs.current[active], false);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [active]);

  return (
    <div
      role="tablist"
      aria-label="Output feed"
      className="relative flex rounded-md border border-line p-0.5"
    >
      <span
        ref={pill}
        aria-hidden
        className="t-tabs-pill rounded-[4px] bg-raised"
      />
      {(Object.keys(FEEDS) as FeedId[]).map((id) => {
        const feed = FEEDS[id];
        const selected = id === active;
        return (
          <button
            key={id}
            ref={(el) => {
              tabs.current[id] = el;
            }}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(id)}
            className={`relative z-10 flex h-7 items-center gap-1.5 rounded-[4px] px-2.5 text-label whitespace-nowrap transition-[color] duration-(--duration-fast) ease-(--ease-smooth-out) focus-visible:outline-2 focus-visible:outline-air ${
              selected ? "text-ink" : "text-ink-3 hover:text-ink-2"
            }`}
          >
            {feed.label.split(" ")[0]}
            <span className="font-mono text-xs text-ink-3">
              {feed.lang.toUpperCase()}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function place(
  pill: HTMLElement | null,
  tab: HTMLElement | null | undefined,
  animate: boolean,
) {
  if (!pill || !tab) return;
  if (!animate) pill.style.transition = "none";
  pill.style.transform = `translateX(${tab.offsetLeft}px)`;
  pill.style.width = `${tab.offsetWidth}px`;
  if (!animate) {
    void pill.offsetWidth; // flush the snapped position before restoring the transition
    pill.style.transition = "";
  }
}
