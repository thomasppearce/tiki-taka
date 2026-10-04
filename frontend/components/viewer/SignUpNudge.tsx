"use client";

import { Check } from "@phosphor-icons/react/dist/ssr";

import { Panel } from "@/components/ui/Panel";
import { useRole } from "@/lib/role";

const PERKS = [
  "Pick your graphics: casual or analyst, English or Spanish",
  "Follow a player on the camera and the tactical view",
  "Every key moment, with the events that justify it",
  "The full stats sheet",
];

/** For guests: what an account adds, and a one-click (simulated) sign-in. */
export function SignUpNudge({ className = "" }: { className?: string }) {
  const [, setRole] = useRole();
  return (
    <Panel title="Watching as a guest" className={className}>
      <div className="flex flex-col gap-3 p-3">
        <ul className="flex flex-col gap-2">
          {PERKS.map((perk) => (
            <li key={perk} className="flex gap-2 text-sm text-ink-2">
              <Check
                size={16}
                weight="bold"
                className="mt-0.5 shrink-0 text-ink-3"
              />
              {perk}
            </li>
          ))}
        </ul>
        <button
          type="button"
          onClick={() => setRole("fan")}
          className="inline-flex h-8 w-fit items-center rounded-md border border-air bg-air px-3 text-label font-medium text-ink-on-fill transition-[background-color,border-color] duration-150 ease-out hover:border-air-hover hover:bg-air-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-air active:translate-y-px"
        >
          Sign in free
        </button>
        <p className="text-xs text-ink-3">
          Accounts are simulated in this demo: signing in switches you to the
          Fan view.
        </p>
      </div>
    </Panel>
  );
}
