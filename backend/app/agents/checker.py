"""The citation checker: deterministic code, not a model, between the Explainer and the queue.

It holds a draft to its brief. Every claim must cite at least one event, every cited event must be
in the brief, and every number in a claim must come from the events it cites (or the match
situation). Every number and player named anywhere in the graphic must appear in the brief. A
draft that fails goes back to the Explainer with the list of problems.

A model checking its own work tends to agree with itself; code that checks against the data
doesn't. That is the part of this team a single agent can't do as well.
"""

import re

from app.agents.brief import MomentBrief, is_close, numbers_in
from app.agents.schemas import Draft, Localized

CAPITALIZED = re.compile(r"\b[A-Z][a-zA-Z'-]+(?:-[A-Z][a-zA-Z'-]+)?\b")


def check_draft(draft: Draft, brief: MomentBrief) -> list[str]:
    """Problems with an English draft; empty if it can go to the queue."""
    problems: list[str] = []
    citable = brief.citable
    situation = numbers_in(brief.situation) | numbers_in(brief.stats)
    if not draft.claims:
        problems.append("The draft makes no claims; every graphic needs at least one cited claim.")
    for claim in draft.claims:
        quoted = f'"{claim.text}"'
        if not claim.evidence_event_ids:
            problems.append(f"{quoted} cites no events.")
            continue
        unknown = [i for i in claim.evidence_event_ids if i not in citable]
        if unknown:
            problems.append(f"{quoted} cites {', '.join(unknown)}, which are not in the brief.")
            continue
        cited = [citable[i] for i in claim.evidence_event_ids]
        allowed = frozenset().union(*(f.numbers for f in cited)) | situation
        allowed |= {float(len(cited))}
        for number in sorted(numbers_in(claim.text)):
            if not is_close(number, allowed):
                problems.append(
                    f"{quoted} says {_fmt(number)}, which its cited events don't support."
                )
    problems += _check_text({"headline": draft.headline, "body": draft.body}, brief)
    return problems


def check_localized(variants: Localized, brief: MomentBrief) -> list[str]:
    """Problems with the four audience and language variants."""
    return _check_text(variants.model_dump(), brief)


def _check_text(fields: dict[str, str], brief: MomentBrief) -> list[str]:
    problems: list[str] = []
    allowed = brief.numbers
    surnames = brief.surnames
    involved = frozenset(
        name for fact in (*brief.evidence, *brief.lead_up) for name in fact.players
    )
    for field, text in fields.items():
        for number in sorted(numbers_in(text)):
            if not is_close(number, allowed):
                problems.append(f"The {field} says {_fmt(number)}, which isn't in the brief.")
        for word in CAPITALIZED.findall(text):
            if word in surnames and word not in involved:
                problems.append(
                    f"The {field} names {word}, who isn't involved in this moment's events."
                )
    return problems


def _fmt(number: float) -> str:
    return str(int(number)) if number == int(number) else str(number)
