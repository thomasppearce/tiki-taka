"""The single-agent baseline for the graphics team (app/agents/team.py).

One agent does the team's whole job in one answer: decide whether the moment deserves a graphic,
write it with every claim citing its events, place it in the queue, and write the four audience
and language variants. So that the comparison is about the structure rather than the wording, it
gets everything the team gets: the same model, the same brief, the same knowledge base with the
same single lookup, the four specialists' instructions word for word, and the checker's rules as
instructions to check its own work. What it doesn't have is anyone else: no checker that sends a
draft back.
"""

from app.agents.brief import MomentBrief
from app.agents.checker import check_draft, check_localized
from app.agents.schemas import Draft, Interpretation, Localized, Placement
from app.agents.team import EXPLAINER, INTERPRETER, LOCALIZER, PRODUCER, AgentTeam


class SoloGraphic(Localized, Placement, Draft, Interpretation):
    """All four answers in one: the Interpreter's fields, then the Explainer's, the Producer's,
    and the Localizer's (pydantic orders inherited fields from the last base to the first)."""


SOLO = f"""You are the whole graphics team on a live football broadcast, working alone. The match
is fictional. Four specialists usually share this work; their instructions follow, word for
word. Do all four jobs and give one answer:
1. as the Interpreter: worth_airing, angle, type, focus_player_id;
2. as the Explainer: headline, body, claims, background_used;
3. as the Producer: priority, shelf_life_seconds, type, reason;
4. as the Localizer: the eight analyst and casual, English and Spanish fields, from your headline
   and body.
Before you answer, check your own work as a fact-checker would: every claim cites ids of events
listed in the brief; every number in a claim comes from the events it cites; every number and
player in the headlines and bodies appears in the brief, and the only players named are those
involved in this moment's events.

THE INTERPRETER'S INSTRUCTIONS
{INTERPRETER}

THE EXPLAINER'S INSTRUCTIONS
{EXPLAINER}

THE PRODUCER'S INSTRUCTIONS
{PRODUCER}

THE LOCALIZER'S INSTRUCTIONS
{LOCALIZER}"""


async def run_solo(team: AgentTeam, brief: MomentBrief) -> tuple[SoloGraphic, int, list[str], str]:
    """One answer from the single agent, its tokens, what the team's checker finds wrong with
    it (empty if it could air with its receipts), and what its knowledge-base lookup found."""
    prompt = f"{brief.text()}\n\n{brief.queue or 'QUEUE: empty. No decisions yet.'}"
    tools = [team.knowledge] if team.knowledge else None
    graphic, tokens, found = await team.ask_with_tools("Solo", SOLO, prompt, SoloGraphic, tools)
    fields = graphic.model_dump()
    problems = check_draft(Draft.model_validate(fields), brief)
    problems += check_localized(Localized.model_validate(fields), brief)
    return graphic, tokens, problems, "\n".join(found)
