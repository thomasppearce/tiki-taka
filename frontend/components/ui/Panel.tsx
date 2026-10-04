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
      className={`flex min-h-0 min-w-0 flex-col rounded-lg border border-line bg-panel ${className}`}
    >
      <header className="flex min-h-10 shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-line px-3 py-2">
        <h2 className="text-label font-medium whitespace-nowrap text-ink-2">
          {title}
        </h2>
        {aside}
      </header>
      {children}
    </section>
  );
}
