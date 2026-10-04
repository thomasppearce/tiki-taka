import type { ReactNode } from "react";

/** A console panel: hairline border, a title row, and content. */
export function Panel({
  title,
  aside,
  children,
  className = "",
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`flex min-h-0 flex-col rounded-lg border border-line bg-panel ${className}`}
    >
      <header className="flex h-10 shrink-0 items-center justify-between gap-3 border-b border-line px-3">
        <h2 className="text-label font-medium text-ink-2">{title}</h2>
        {aside}
      </header>
      {children}
    </section>
  );
}
