"use client";

import {
  ChartBar,
  ClockCounterClockwise,
  IdentificationBadge,
  Quotes,
  Receipt,
  Strategy,
  Timer,
} from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";
import { type FormEvent, type KeyboardEvent, useId, useState } from "react";

import { Button } from "@/components/ui/Button";
import { SwapText } from "@/components/ui/SwapText";
import type { Proposal } from "@/lib/contracts.generated";
import { FEEDS, type FeedId } from "@/lib/controlRoom";
import { formatCountdown } from "@/lib/format";
import { forFeed } from "@/lib/i18n";

const TYPE_META: Record<Proposal["type"], { label: string; Icon: Icon }> = {
  stat_graphic: { label: "Stat graphic", Icon: ChartBar },
  narrative_line: { label: "Narrative line", Icon: Quotes },
  tactical_insight: { label: "Tactical insight", Icon: Strategy },
  player_tag: { label: "Player tag", Icon: IdentificationBadge },
  recap_beat: { label: "Recap beat", Icon: ClockCounterClockwise },
};

const URGENT_MS = 20_000;

export type CardActions = {
  onSelect: (id: string) => void;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onEdit: (id: string) => void;
  onCancelEdit: () => void;
  onSaveEdit: (id: string, headline: string, body: string) => void;
};

/**
 * One proposal in the producer's queue, written for the active feed. Selecting a card lights up
 * its evidence on the pitch; the selected card shows its receipts and the actions.
 */
export function ProposalCard({
  proposal,
  clockMs,
  feed,
  selected,
  editing,
  actions,
}: {
  proposal: Proposal;
  clockMs: number;
  feed: FeedId;
  selected: boolean;
  editing: boolean;
  actions: CardActions;
}) {
  const { label, Icon } = TYPE_META[proposal.type];
  const { audience, lang } = FEEDS[feed];
  const remainingMs = proposal.expires_at_clock_ms - clockMs;
  const urgent = remainingMs <= URGENT_MS;
  const id = proposal.proposal_id;
  const headline = forFeed(proposal.headline, audience, lang);
  const body = forFeed(proposal.body, audience, lang);

  return (
    <article
      tabIndex={0}
      aria-current={selected || undefined}
      aria-label={headline}
      onClick={() => actions.onSelect(id)}
      onKeyDown={(e) => {
        if (
          e.target === e.currentTarget &&
          (e.key === "Enter" || e.key === " ")
        ) {
          e.preventDefault();
          actions.onSelect(id);
        }
      }}
      className={`cursor-pointer rounded-md border p-3 transition-[border-color,background-color] duration-(--duration-quick) ease-(--ease-smooth-out) focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-air ${
        selected
          ? "border-air bg-raised"
          : "border-line hover:border-line-strong"
      }`}
    >
      <header className="flex items-center justify-between text-xs text-ink-3">
        <span className="flex items-center gap-1.5">
          <Icon size={14} />
          {label}
          {proposal.status === "edited" && (
            <span className="text-ink-2">(edited)</span>
          )}
        </span>
        <span
          className={`flex items-center gap-1 font-mono tabular-nums transition-[color] duration-(--duration-fast) ${urgent ? "text-warning" : ""}`}
        >
          <Timer size={14} weight={urgent ? "bold" : "regular"} />
          <span className="sr-only">Expires in</span>
          {formatCountdown(remainingMs)}
        </span>
      </header>

      {editing ? (
        <EditForm
          id={id}
          headline={headline}
          body={body}
          feedLabel={FEEDS[feed].label}
          actions={actions}
        />
      ) : (
        <>
          <SwapText
            as="h3"
            text={headline}
            className="mt-2 text-base leading-snug font-semibold text-ink"
          />
          <SwapText
            as="p"
            text={body}
            className="mt-1 text-sm leading-relaxed text-ink-2"
          />
        </>
      )}

      {selected && !editing && (
        <ul className="mt-3 space-y-2 border-t border-line pt-3">
          {proposal.claims.map((claim) => (
            <li
              key={claim.text}
              className="flex items-start gap-2 text-label text-ink-2"
            >
              <Receipt size={14} className="mt-0.5 shrink-0 text-ink-3" />
              <span className="flex-1">{claim.text}</span>
              <span className="shrink-0 rounded-md border border-air/60 px-1.5 text-xs text-ink-2 tabular-nums">
                {claim.evidence_event_ids.length}{" "}
                {claim.evidence_event_ids.length === 1 ? "event" : "events"}
              </span>
            </li>
          ))}
        </ul>
      )}

      {!editing && (
        <footer className="mt-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
          <span className="text-xs text-ink-3">
            <span className="font-mono text-ink-2 tabular-nums">
              {Math.round(proposal.confidence * 100)}%
            </span>{" "}
            confidence
          </span>
          {selected ? (
            <div className="flex gap-1.5" onClick={(e) => e.stopPropagation()}>
              <Button shortcut="R" onClick={() => actions.onReject(id)}>
                Reject
              </Button>
              <Button shortcut="E" onClick={() => actions.onEdit(id)}>
                Edit
              </Button>
              <Button
                variant="primary"
                shortcut="A"
                onClick={() => actions.onApprove(id)}
              >
                Approve
              </Button>
            </div>
          ) : (
            <span className="text-xs text-ink-3">
              {proposal.claims.length}{" "}
              {proposal.claims.length === 1 ? "claim" : "claims"}
            </span>
          )}
        </footer>
      )}
    </article>
  );
}

function EditForm({
  id,
  headline,
  body,
  feedLabel,
  actions,
}: {
  id: string;
  headline: string;
  body: string;
  feedLabel: string;
  actions: CardActions;
}) {
  const [draftHeadline, setDraftHeadline] = useState(headline);
  const [draftBody, setDraftBody] = useState(body);
  const fieldId = useId();
  const save = (e?: FormEvent) => {
    e?.preventDefault();
    if (draftHeadline.trim() && draftBody.trim()) {
      actions.onSaveEdit(id, draftHeadline.trim(), draftBody.trim());
    }
  };
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Escape") actions.onCancelEdit();
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) save();
  };
  const field =
    "w-full rounded-md border border-line bg-page px-2 py-1.5 text-ink focus-visible:border-air focus-visible:outline-none";

  return (
    <form
      onSubmit={save}
      onKeyDown={onKeyDown}
      onClick={(e) => e.stopPropagation()}
      className="mt-2 space-y-2"
    >
      <p className="text-xs text-ink-3">Editing the {feedLabel} copy</p>
      <label
        htmlFor={`${fieldId}-headline`}
        className="block text-xs text-ink-2"
      >
        Headline
      </label>
      <input
        id={`${fieldId}-headline`}
        autoFocus
        value={draftHeadline}
        onChange={(e) => setDraftHeadline(e.target.value)}
        className={`${field} text-sm font-semibold`}
      />
      <label htmlFor={`${fieldId}-body`} className="block text-xs text-ink-2">
        Body
      </label>
      <textarea
        id={`${fieldId}-body`}
        rows={3}
        value={draftBody}
        onChange={(e) => setDraftBody(e.target.value)}
        className={`${field} resize-none text-sm leading-relaxed`}
      />
      <div className="flex justify-end gap-1.5 pt-1">
        <Button onClick={actions.onCancelEdit} shortcut="Esc">
          Cancel
        </Button>
        <Button type="submit" variant="primary">
          Save and approve
        </Button>
      </div>
    </form>
  );
}
