"use client";

import { Segmented } from "@/components/ui/Segmented";
import { FEEDS, type FeedId } from "@/lib/controlRoom";

/** Output-feed switcher: which feed's graphics the producer is previewing. */
export function FeedTabs({
  active,
  onChange,
}: {
  active: FeedId;
  onChange: (feed: FeedId) => void;
}) {
  return (
    <Segmented
      label="Output feed"
      value={active}
      onChange={onChange}
      options={(Object.keys(FEEDS) as FeedId[]).map((id) => ({
        value: id,
        label: (
          <>
            {FEEDS[id].label.split(" ")[0]}
            <span className="font-mono text-xs text-ink-3">
              {FEEDS[id].lang.toUpperCase()}
            </span>
          </>
        ),
      }))}
    />
  );
}
