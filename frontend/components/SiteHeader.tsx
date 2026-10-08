import { SoccerBall } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import type { ReactNode } from "react";

import { RoleSwitch } from "@/components/RoleSwitch";

/** The app bar for viewers: home link, whatever the page puts in the middle, and the role. */
export function SiteHeader({ children }: { children?: ReactNode }) {
  return (
    <header className="flex min-h-12 shrink-0 flex-wrap items-center gap-x-6 gap-y-2 border-b border-line bg-panel px-4 py-2">
      <Link
        href="/"
        className="flex items-center gap-2 rounded-md text-sm font-semibold whitespace-nowrap text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-air"
      >
        <SoccerBall size={18} weight="bold" className="text-ink-2" />
        Tiki-Taka
      </Link>
      {children}
      <div className="ml-auto">
        <RoleSwitch />
      </div>
    </header>
  );
}
