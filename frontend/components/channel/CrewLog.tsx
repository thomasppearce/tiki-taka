"use client";

import {
  Code,
  Eye,
  FilmSlate,
  SealCheck,
  UserCircle,
} from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";

import {
  type DrillTarget,
  FailureDrill,
} from "@/components/control-room/FailureDrill";
import { Panel } from "@/components/ui/Panel";
import type { Channel, ChannelLog } from "@/lib/contracts.generated";

/** The channel's model agents, for the failure drill. */
const CHANNEL_CREW: DrillTarget[] = [
  {
    agent: "watcher",
    label: "Watchers",
    fallback: "each match's last story stands",
  },
  {
    agent: "director",
    label: "Director",
    fallback: "the cut goes ahead on the code's pick",
  },
];

const AGENT: Record<ChannelLog["agent"], { label: string; icon: Icon }> = {
  director: { label: "Director", icon: FilmSlate },
  watcher: { label: "Watcher", icon: Eye },
  checker: { label: "Checker", icon: SealCheck },
  producer: { label: "Producer", icon: UserCircle },
  code: { label: "Signals", icon: Code },
};

/**
 * The channel's crew at work, newest first: the Watchers retelling their matches, the Director
 * choosing cuts (and what it passed over), the checker rejecting what it can't verify, and the
 * producer's calls.
 */
export function CrewLog({
  channel,
  fixtureOf,
}: {
  channel: Channel;
  fixtureOf: (matchId: string) => string;
}) {
  return (
    <Panel
      title="The crew"
      aside={
        <span className="text-xs text-ink-3">
          {channel.agents
            ? "Watcher and Director agents on Microsoft Foundry"
            : "Agents off: the code writes every package"}
        </span>
      }
    >
      {channel.agents && <FailureDrill targets={CHANNEL_CREW} />}
      {channel.log.length ? (
        <ol className="max-h-[26rem] overflow-y-auto px-3">
          {channel.log.map((entry, i) => {
            const { label, icon: Glyph } = AGENT[entry.agent];
            return (
              <li
                key={`${entry.clock_ms}-${i}`}
                className="border-b border-line py-2 last:border-b-0"
              >
                <p className="flex items-center gap-2 text-xs leading-5">
                  <span className="w-7 shrink-0 font-mono text-ink-3 tabular-nums">
                    {`${Math.floor(entry.clock_ms / 60_000) + 1}'`}
                  </span>
                  <span className="flex shrink-0 items-center gap-1.5 text-ink">
                    <Glyph size={14} />
                    {label}
                  </span>
                  {entry.match_id && (
                    <span className="truncate text-ink-3">
                      {fixtureOf(entry.match_id)}
                    </span>
                  )}
                </p>
                <p className="mt-0.5 pl-9 text-sm text-ink-2">{entry.detail}</p>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="p-3 text-sm text-ink-3">
          The crew&rsquo;s work appears here: every story a Watcher tells, every
          cut the Director chooses, and every answer the checker sends back.
        </p>
      )}
    </Panel>
  );
}
