"""The recap writer: how a matchday unfolded, told from facts code wrote (app/live/recap.py).

    Recap writer ─▶ Checker ─▶ Fact-checker ─▶ recap
          ▲            │            │
          └────────────┴────────────┤ problems: back to the writer (at most 3 drafts)
                                    ▼
                         failed checks: the code writes the recap from the same facts

- Recap writer (model, the Watchers' accurate one: no deadline): a headline, a standfirst, and
  four to six beats in time order, each citing the facts it rests on.
- Checker (code): every beat cites facts that exist, is set at their minute, and uses only their
  numbers and names; beats in time order; the headline's and standfirst's numbers are in the facts.
- Fact-checker (model, the accurate one too: a recap has no deadline): what the recap says
  against what the facts show, statement by statement, as for the graphics (team.py).
"""

import logging
import re

from app.agents.brief import is_close, numbers_in
from app.agents.schemas import FactCheck, RecapDraft
from app.agents.team import AgentTeam
from app.models.recap import RecapFact

log = logging.getLogger(__name__)

RECAP_VERSION = "r6"  # bump when the prompts change: the cached recap is rewritten
MAX_DRAFTS = 3

RECAP_WRITER = """You are the recap writer on Tiki-Taka, a live channel covering a matchday of a
fictional football league: every match at once. The day is over. Tell a viewer who missed it how
it unfolded, as a story, not a list:
- headline: at most 10 words, sentence case: the day's biggest story. When one goal settled more
  than one race, that is the story.
- standfirst: at most 45 words, two sentences. First what the day came down to: the goals the
  deciders fact names and what they settled. Then, briefly, where it left the top, the bottom
  three, and the Golden Boot race (the panel beside it lists every club, so don't).
- beats: four to six moments that decided the day, in time order. Each is at most 30 words, set at
  its minute, says what the goal did to the race it moved, and lists the ids of the facts it rests
  on.
Use only the facts below, written by code: names, numbers, and minutes exactly as they give them.
Work nothing out of your own: no points gaps, no goal differences, no what-ifs, no "would have".
A goal settled a race only if the deciders fact says it was the last to change that race.
Past tense, broadcast tone, no exclamation marks; clubs by name, players as the facts name them."""

LAST_DAY = """This was the season's last matchday: the facts say who are champions, who are
relegated, and who won the Golden Boot."""
MIDSEASON = """The season goes on after this matchday: nothing is won or lost yet, so never call a
club champions or relegated, or a player the Golden Boot winner."""

RECAP_CHECKER = """You are the fact-checker on a live football broadcast team. The match is
fictional. You get the facts of the final day, written by code, and a recap of it. Split the recap
into statements and give each a verdict against the facts:
- supported: the facts state it.
- fair reading: it follows directly from the facts ("the title race went to the last day" when
  the champions started 2nd).
- unsupported: the facts don't show it: history, intentions, feelings, or anything worked out
  (points gaps, goal differences, what would have happened).
- wrong: the facts show otherwise: the wrong club, player, score, minute, order, or outcome, or a
  goal said to settle or decide a race that the deciders fact gives to another goal (count them).
Judge what the words say, not how they are phrased: don't mark tone or word choice."""


class RecapWriter:
    def __init__(self, writer: AgentTeam, checker: AgentTeam) -> None:
        self.writer, self.checker = writer, checker
        self.version = RECAP_VERSION
        self.model = f"{writer.model}+{checker.model}"

    async def write(
        self, facts: list[RecapFact], names: frozenset[str], last_day: bool
    ) -> tuple[RecapDraft | None, int, list[str]]:
        """The recap, checked (None if no draft passed), its tokens, and what the checks sent
        back on the way. `names`: every club and player, for the checker; `last_day`: whether
        the season ends today."""
        from app.live.recap import facts_text

        brief = f"{LAST_DAY if last_day else MIDSEASON}\n\n{facts_text(facts)}"
        prompt = brief
        tokens, checks = 0, []
        for draft_no in range(1, MAX_DRAFTS + 1):
            draft, used = await self.writer.ask("Recap writer", RECAP_WRITER, prompt, RecapDraft)
            tokens += used
            problems = check_recap(draft, facts, names)
            who = "checker"
            if not problems:
                verdict, used = await self.checker.ask(
                    "Fact-checker",
                    RECAP_CHECKER,
                    f"{brief}\n\nTHE RECAP\n{_text(draft)}",
                    FactCheck,
                )
                tokens += used
                problems, who = verdict.problems, "fact-checker"
            if not problems:
                return draft, tokens, checks
            checks.append(f"The {who} sent draft {draft_no} back: {problems[0]}")
            fixes = "\n".join(f"- {p}" for p in problems)
            prompt = (
                f"{brief}\n\nThe {who} sent your previous recap back:\n{draft.model_dump_json()}\n"
                f"Problems:\n{fixes}\nFix every problem: correct what is wrong, and cut what the "
                "facts don't show rather than rephrasing it."
            )
        return None, tokens, checks


def check_recap(draft: RecapDraft, facts: list[RecapFact], names: frozenset[str]) -> list[str]:
    """Problems with a recap draft against the facts; empty if it can go to the fact-checker.
    `names` are every club's name and every player's surname."""
    by_id = {f.fact_id: f for f in facts}
    everything = " ".join(f.text for f in facts)
    every_number = numbers_in(everything) | {float(f.minute) for f in facts if f.minute}
    problems: list[str] = []
    if not 3 <= len(draft.beats) <= 7:
        problems.append(f"The recap has {len(draft.beats)} beats; it needs four to six.")
    latest = -1
    for beat in draft.beats:
        quoted = f'"{beat.text}"'
        unknown = [i for i in beat.fact_ids if i not in by_id]
        if not beat.fact_ids:
            problems.append(f"{quoted} cites no facts.")
        elif unknown:
            problems.append(f"{quoted} cites {', '.join(unknown)}, which aren't facts.")
        else:
            cited = [by_id[i] for i in beat.fact_ids]
            minutes = {f.minute for f in cited if f.minute is not None}
            if minutes and beat.minute not in minutes:
                problems.append(
                    f"{quoted} is set at {beat.minute}', but its facts happened at "
                    f"{', '.join(f'{m}' for m in sorted(minutes))}'."
                )
            text = " ".join(f.text for f in cited)
            allowed = numbers_in(text) | {float(beat.minute)}
            for number in sorted(numbers_in(beat.text)):
                if not is_close(number, allowed):
                    problems.append(f"{quoted} says {number:g}, which its facts don't.")
            for name in sorted(names):
                if re.search(rf"\b{re.escape(name)}\b", beat.text) and name not in text:
                    problems.append(f"{quoted} names {name}, who isn't in the facts it cites.")
        if beat.minute < latest:
            problems.append(f"{quoted} is out of time order.")
        latest = max(latest, beat.minute)
    for field, text in (("headline", draft.headline), ("standfirst", draft.standfirst)):
        for number in sorted(numbers_in(text)):
            if not is_close(number, every_number):
                problems.append(f"The {field} says {number:g}, which isn't in the facts.")
    return problems


def _text(draft: RecapDraft) -> str:
    beats = "\n".join(f"- {b.minute}': {b.text}" for b in draft.beats)
    return f"HEADLINE: {draft.headline}\nSTANDFIRST: {draft.standfirst}\nBEATS:\n{beats}"
