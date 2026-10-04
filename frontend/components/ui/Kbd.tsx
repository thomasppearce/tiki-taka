import type { ReactNode } from "react";

/** A keyboard key hint, e.g. the A in "Approve A". */
export function Kbd({
  children,
  onFill = false,
}: {
  children: ReactNode;
  onFill?: boolean;
}) {
  return (
    <kbd
      className={`inline-flex size-4.5 items-center justify-center rounded-[4px] border font-mono text-[11px] leading-none ${
        onFill
          ? "border-ink-on-fill/30 text-ink-on-fill"
          : "border-line-strong text-ink-3"
      }`}
    >
      {children}
    </kbd>
  );
}
