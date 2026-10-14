"""The channel's agents: a Watcher per match and the Director, on the same Foundry client as the
graphics team (app/agents/team.py).

Each agent gets the model that fits its job: the Watchers have no deadline, so they can use a
slower, more accurate model (gpt-6-luna); the Director must answer inside a five-second
countdown, so it uses the fast one (gpt-5.4-mini). Measured on the same briefs: luna passed the
checker first time on 39 of 40 stories (gpt-5.4-mini 33) but took a median 7.7 s per decision.

- Watcher (model): the story of its match so far on the pitch, for a viewer the channel is about
  to cut to. It never sees the table: models reasoning about who goes up or down got it wrong.
- Director (model): where to cut, from the code's top candidates, weighing how hard a side is
  pushing against what a goal would change in the table; then why we're going there, and what's
  at stake, citing that match's events.
- Checker (code): holds every story and decision to its brief (app/agents/channel_checker.py).
  A rejected answer gets one retry with the problems; after that the channel keeps the
  code-written version.
"""

from collections.abc import Sequence

from app.agents.channel_brief import MatchBrief
from app.agents.channel_checker import check_decision, check_match_recap, check_story
from app.agents.schemas import CutDecision, FactCheck, MatchRecapDraft, StoryUpdate
from app.agents.team import FACT_CHECKER, AgentTeam, Reporter

MAX_RECAP_DRAFTS = 3

CHANNEL_PROMPT_VERSION = "c12"  # bump when prompts or runs change: cached runs regenerate

CHANNEL = """Tiki-Taka is a live channel covering the final day of a fictional football league:
ten matches at once, with the title, the last relegation place, and fourth place still to be
decided."""

RULES = """Rules: use only facts in the brief and never invent a statistic. Claims are for what
happened on the pitch: each one cites the ids of the brief's events that prove it. The score, the
minute, and the AS IT STANDS, AT STAKE, and TABLE MOVES lines are context, written by code: use
them in your text, but never list them as claims. A goal changes the table only as its TABLE MOVES
line says; AT STAKE is about the next goal, not one already scored. PRESSURE NOW is for your
judgment. GOALS SO FAR says what each goal did (an opener, an equaliser, a side back in front): use
it, and never describe how the lead changed hands any other way. Numbers only from the brief, and
minutes written as the brief writes them (33'); a side that leads says its own goals first
(Lanterne Port FC lead 2-1, never 1-2). PLAYER STORIES (the Golden Boot race, a milestone, a
farewell, a player against his old club) are context written by code: use one when it adds to the
story, never list it as a claim, and never invent a player story or a season statistic. Never work
anything out that the brief doesn't say: no points gaps, no goal differences, no consequences of
your own. Present tense, broadcast tone, no exclamation marks; names (players, clubs) capitalized
as in the brief, and clubs by name, never by their three-letter codes."""

WATCHER = f"""{CHANNEL}
You are the Watcher for one match. Write its story so far on the pitch for a viewer the channel
is about to cut to: at most 35 words, about what has happened: the score as it is now (as the
MATCH line gives it), the goals, who is on top, the chances, the cards. The channel shows the
table and what is at stake beside your story, so never mention the table, positions, points,
zones, or the title.
{RULES}"""

DIRECTOR = f"""{CHANNEL}
You are the Director, deciding where the channel cuts. The code proposes the first candidate; the
others are the next best. Choose the match whose next few minutes matter most to the title, the
last relegation place, fourth place, or the Golden Boot race, weighing PRESSURE NOW (how hard a
side is pushing) against AT STAKE (what a goal would change). Keep the proposal unless another
candidate is clearly the bigger story. Then, for the match you choose, write:
- why: at most 18 words, why we're going there now;
- at_stake: at most 25 words, that match's AT STAKE line in plain words, or null if a goal there
  changes nothing; keep exactly who climbs and who drops for each scorer, as the line says;
- claims: every factual statement in why, citing that match's event ids.
{RULES}"""

DIRECTOR_GOAL = f"""{CHANNEL}
You are the Director. The channel is cutting to a goal. Write:
- why: at most 18 words: who scored, for whom, and what it means;
- at_stake: at most 25 words: what the goal changed in the table (its TABLE MOVES line), or what
  is still to play for (an AT STAKE line), or null;
- claims: every factual statement in why, citing the match's event ids.
Set match_id to the match's id.
{RULES}"""


WATCHER_RECAP = f"""{CHANNEL}
You are the Watcher for one match, and it has ended. Write its recap for a viewer who missed it:
- headline: at most 10 words, sentence case: the match's story.
- story: at most 50 words: the final score as the MATCH line gives it, the goals and what each did
  (GOALS SO FAR), who was on top (STATS), the big chances, and the cards.
- claims: every statement about what happened on the pitch, each citing the ids of the events
  that prove it.
The channel's matchday recap says what the results did to the table, so never mention the table,
positions, points, zones, or the title.
{RULES}
The match is over: write in the past tense."""


class ChannelTeam:
    def __init__(self, team: AgentTeam, watchers: AgentTeam | None = None) -> None:
        self.team = team  # the Director's
        self.watchers = watchers or team
        self.model = team.model if self.watchers is team else f"{team.model}+{self.watchers.model}"

    async def story(
        self, brief: MatchBrief, report: Reporter | None = None
    ) -> tuple[StoryUpdate | None, int, list[str], list[str]]:
        """The Watcher's story, checked; None if it fails the checker twice. Also what the checker
        found in the first draft, if it sent it back."""
        prompt = brief.text(watcher=True)
        update, tokens = await self.watchers.ask("Watcher", WATCHER, prompt, StoryUpdate, report)
        update = _receipts_only(update)
        problems = sent_back = check_story(update, brief)
        if problems:
            update, more = await self.watchers.ask(
                "Watcher",
                WATCHER,
                _redo(prompt, update.model_dump_json(), problems),
                StoryUpdate,
                report,
            )
            tokens += more
            update = _receipts_only(update)
            problems = check_story(update, brief)
        return (None if problems else update), tokens, problems, sent_back

    async def decide(
        self,
        reason: str,
        on_air: str,
        briefs: Sequence[MatchBrief],
        report: Reporter | None = None,
    ) -> tuple[CutDecision | None, int, list[str], list[str]]:
        """The Director's choice and words, checked; None if it fails the checker twice. Also what
        the checker found in the first draft, if it sent it back."""
        goal = reason == "goal"
        candidates = "\n\n".join(b.text(label=f"[{i + 1}] ") for i, b in enumerate(briefs))
        prompt = f"ON AIR NOW: {on_air}\nWHY THE CODE WANTS TO CUT: {reason}\n\n{candidates}"
        instructions = DIRECTOR_GOAL if goal else DIRECTOR
        decision, tokens = await self.team.ask(
            "Director", instructions, prompt, CutDecision, report
        )
        decision = _receipts_only(decision)
        problems = sent_back = check_decision(decision, briefs)
        if problems:
            decision, more = await self.team.ask(
                "Director",
                instructions,
                _redo(prompt, decision.model_dump_json(), problems),
                CutDecision,
                report,
            )
            tokens += more
            decision = _receipts_only(decision)
            problems = check_decision(decision, briefs)
        return (None if problems else decision), tokens, problems, sent_back

    async def recap(
        self, brief: MatchBrief, report: Reporter | None = None
    ) -> tuple[MatchRecapDraft | None, int, list[str]]:
        """The Watcher's recap of its match, from the whole match's brief: checked by code and
        by the fact-checker, up to three drafts. None if none passes (the code writes it then).
        Also what the checks sent back on the way."""
        base = brief.text(watcher=True)
        prompt, tokens, checks = base, 0, []
        for n in range(1, MAX_RECAP_DRAFTS + 1):
            draft, used = await self.watchers.ask(
                "Watcher", WATCHER_RECAP, prompt, MatchRecapDraft, report
            )
            tokens += used
            draft = _receipts_only(draft)
            problems, who = check_match_recap(draft, brief), "checker"
            if not problems:
                verdict, used = await self.team.ask(
                    "Fact-checker",
                    FACT_CHECKER,
                    f"{base}\n\nTHE GRAPHIC\nHEADLINE: {draft.headline}\nBODY: {draft.story}",
                    FactCheck,
                    report,
                )
                tokens += used
                problems, who = verdict.problems, "fact-checker"
            if not problems:
                return draft, tokens, checks
            checks.append(f"The {who} sent draft {n} back: {problems[0]}")
            prompt = _redo(base, draft.model_dump_json(), problems)
        return None, tokens, checks


def _receipts_only[A: (StoryUpdate, CutDecision, MatchRecapDraft)](answer: A) -> A:
    """Claims are receipts for what happened on the pitch. A claim that cites nothing is the
    model restating context (the score, the table): the text that says it is still checked, so
    it is dropped rather than failed."""
    return answer.model_copy(update={"claims": [c for c in answer.claims if c.evidence_event_ids]})


def _redo(prompt: str, answer: str, problems: list[str]) -> str:
    fixes = "\n".join(f"- {p}" for p in problems)
    return (
        f"{prompt}\n\nThe checker rejected your answer:\n{answer}\n"
        f"Problems:\n{fixes}\nFix every problem."
    )
