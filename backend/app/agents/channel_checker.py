"""The checker for the channel's agents: the same rules as for graphics (app/agents/checker.py),
held against a match brief. Every claim cites events from the brief, and its numbers come from
those events, the situation, or the code-written stakes; every number in the text is in the
brief; every player named played a part in the brief's events. A Watcher's story gives the score
as it is now, never a scoreline the match hasn't been, and never talks about the table. The
Director may only choose one of its candidates."""

import re
from collections.abc import Sequence

from app.agents.brief import is_close, numbers_in
from app.agents.channel_brief import MatchBrief
from app.agents.checker import CAPITALIZED
from app.agents.schemas import CutDecision, DraftClaim, MatchRecapDraft, StoryUpdate

# Words that only make sense about the table ("2nd half" is the match, "top corner" the goal).
TABLE_TALK = re.compile(
    r"\b(?:relegat\w*|zones?|table|points?|title|champions?|continental|top four|safety|"
    r"survival|(?:go|goes|stay|stays|move|moves|sit|sits) (?:top|bottom)(?! of the Golden Boot)|"
    # ordinals are table talk, unless they count a player's goals or the match's half
    r"\d+(?:st|nd|rd|th)\b(?! half| league goal| goal| of the season))",
    re.IGNORECASE,
)
SCORELINE = re.compile(r"\b(\d+)\s*[-–]\s*(\d+)\b")
# How a lead changed hands: only true if the brief's GOALS SO FAR says so.
BACK_IN_FRONT = re.compile(
    r"\b(?:(?:ahead|in front|lead|leads|led)\s+again|back in front|restor\w* (?:the|their) lead|"
    r"regain\w*(?: the)? lead)\b",
    re.IGNORECASE,
)
EQUALISER = re.compile(r"\bequali[sz]\w*", re.IGNORECASE)


def check_story(update: StoryUpdate, brief: MatchBrief) -> list[str]:
    """A story is about the pitch: the Watcher never sees the table, so any table talk in it is
    made up."""
    problems = _check(brief, update.claims, {"story": update.story})
    home, away = now = brief.scores[-1]
    told = {(int(h), int(a)) for h, a in SCORELINE.findall(update.story)}
    if not told & {now, (away, home)}:
        problems.append(f"The story doesn't give the score as it is now: {home}-{away}.")
    passed = set(brief.scores) | {(a, h) for h, a in brief.scores}
    for h, a in sorted(told - passed):
        problems.append(f"The story says {h}-{a}, which this match has never been.")
    talk = sorted({m.group(0).lower() for m in TABLE_TALK.finditer(update.story)})
    if talk:
        words = ", ".join(f'"{w}"' for w in talk)
        problems.append(
            f"The story talks about the table ({words}); tell the story on the pitch only."
        )
    return problems


def check_match_recap(recap: MatchRecapDraft, brief: MatchBrief) -> list[str]:
    """A recap, like a story, is about the pitch, and gives the final score."""
    fields = {"headline": recap.headline, "story": recap.story}
    problems = _check(brief, recap.claims, fields)
    home, away = final = brief.scores[-1]
    told = {(int(h), int(a)) for text in fields.values() for h, a in SCORELINE.findall(text)}
    told -= _stat_pairs(brief.stats)  # "8-4 on target" is a comparison, not a scoreline
    if not told & {final, (away, home)}:
        problems.append(f"The recap doesn't give the final score: {home}-{away}.")
    passed = set(brief.scores) | {(a, h) for h, a in brief.scores}
    for h, a in sorted(told - passed):
        problems.append(f"The recap says {h}-{a}, which this match never was.")
    talk = sorted({m.group(0).lower() for t in fields.values() for m in TABLE_TALK.finditer(t)})
    if talk:
        words = ", ".join(f'"{w}"' for w in talk)
        problems.append(
            f"The recap talks about the table ({words}); the matchday recap covers that."
        )
    return problems


def _stat_pairs(stats: str) -> set[tuple[int, int]]:
    """Each stat as both sides' whole numbers, either way round: (11, 7) shots, (8, 4) on
    target. A recap may compare them the way it gives a score."""
    if ";" not in stats:
        return set()
    home, away = (
        [int(float(n)) for n in re.findall(r"\d+(?:\.\d+)?", side) if "." not in n]
        for side in stats.split(";", 1)
    )
    return {pair for h, a in zip(home, away, strict=False) for pair in ((h, a), (a, h))}


def check_decision(decision: CutDecision, briefs: Sequence[MatchBrief]) -> list[str]:
    brief = next((b for b in briefs if b.match_id == decision.match_id), None)
    if brief is None:
        options = ", ".join(b.match_id for b in briefs)
        return [f"{decision.match_id} is not a candidate; choose one of {options}."]
    text = {"why": decision.why, "at_stake": decision.at_stake or ""}
    problems = _check(brief, decision.claims, text)
    if not brief.stakes and not brief.moves:
        # Nothing in the table rides on this match: "the title picture" here is made up.
        talk = sorted({m.group(0).lower() for t in text.values() for m in TABLE_TALK.finditer(t)})
        if talk:
            words = ", ".join(f'"{w}"' for w in talk)
            problems.append(
                f"Nothing in the table is at stake in this match (the next goal changes nothing), "
                f"but the cut talks about it ({words}); say why on the pitch, and leave at_stake "
                "null."
            )
    return problems


def _check(brief: MatchBrief, claims: list[DraftClaim], text: dict[str, str]) -> list[str]:
    problems: list[str] = []
    citable = brief.citable
    general = numbers_in(
        " ".join((brief.situation, brief.standing, *brief.stakes, *brief.moves, *brief.stories))
    )
    for claim in claims:
        quoted = f'"{claim.text}"'
        if not claim.evidence_event_ids:
            problems.append(f"{quoted} cites no events.")
            continue
        unknown = [i for i in claim.evidence_event_ids if i not in citable]
        if unknown:
            problems.append(f"{quoted} cites {', '.join(unknown)}, which are not in the brief.")
            continue
        cited = [citable[i] for i in claim.evidence_event_ids]
        allowed = frozenset().union(*(f.numbers for f in cited)) | general | {float(len(cited))}
        for number in sorted(numbers_in(claim.text)):
            if not is_close(number, allowed):
                problems.append(
                    f"{quoted} says {_fmt(number)}, which its cited events don't support."
                )
    allowed = brief.numbers
    involved = brief.involved
    history = " ".join(brief.goals)
    for field, value in text.items():
        again = BACK_IN_FRONT.search(value)
        if again and "back in front" not in history:
            problems.append(
                f'The {field} says "{again.group(0)}", but nobody has gone back in front in this '
                "match: see GOALS SO FAR."
            )
        if EQUALISER.search(value) and "equaliser" not in history:
            problems.append(
                f"The {field} mentions an equaliser, but there hasn't been one: see GOALS SO FAR."
            )
        for number in sorted(numbers_in(value)):
            if not is_close(number, allowed):
                problems.append(f"The {field} says {_fmt(number)}, which isn't in the brief.")
        for word in CAPITALIZED.findall(value):
            if word in brief.surnames and word not in involved:
                problems.append(f"The {field} names {word}, who isn't in the brief's events.")
    return problems


def _fmt(number: float) -> str:
    return str(int(number)) if number == int(number) else str(number)
