"use client";

import { type ReactNode, useEffect, useLayoutEffect, useRef } from "react";

export type SegmentOption<T extends string> = {
  value: T;
  label: ReactNode;
};

/**
 * A segmented control with the transitions.dev sliding pill: the pill is measured from the active
 * option and slides between options; on first paint and on resize it snaps without a transition.
 */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  size = "md",
}: {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  size?: "sm" | "md";
}) {
  const pill = useRef<HTMLSpanElement>(null);
  const tabs = useRef<Partial<Record<T, HTMLButtonElement | null>>>({});
  const placed = useRef(false);

  useLayoutEffect(() => {
    const animate = placed.current;
    place(pill.current, tabs.current[value], animate);
    placed.current = true;
  }, [value]);

  useEffect(() => {
    const onResize = () => place(pill.current, tabs.current[value], false);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [value]);

  return (
    <div
      role="tablist"
      aria-label={label}
      className="relative flex rounded-md border border-line p-0.5"
    >
      <span
        ref={pill}
        aria-hidden
        className="t-tabs-pill rounded-[4px] bg-raised"
      />
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            ref={(el) => {
              tabs.current[option.value] = el;
            }}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(option.value)}
            className={`relative z-10 flex items-center gap-1.5 rounded-[4px] text-label whitespace-nowrap transition-[color] duration-(--duration-fast) ease-(--ease-smooth-out) focus-visible:outline-2 focus-visible:outline-air ${
              size === "sm" ? "h-6 px-2" : "h-7 px-2.5"
            } ${selected ? "text-ink" : "text-ink-3 hover:text-ink-2"}`}
          >
            {option.label}
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
