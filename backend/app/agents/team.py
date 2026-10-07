"""The agent team, as a Microsoft Agent Framework workflow on Microsoft Foundry.

One run per moment:

    Interpreter ─▶ Explainer ─▶ Checker ─▶ Producer ─▶ Localizer ─▶ proposal
         │             ▲           │
         │             └───────────┤ problems: back to the Explainer (at most 3 drafts)
         ▼                         ▼
      passed               failed checks (the desk falls back to its scripted copy)

- Interpreter (model): is the moment worth a graphic now, and what is its angle?
- Explainer (model): headline, body, and claims, each citing the events that prove it.
- Checker (code): every id, number, and name against the brief. A model checking its own work
  tends to agree with itself; this doesn't.
- Producer (model): priority and shelf life, given the live queue and what this producer has
  approved and rejected.
- Localizer (model): analyst and casual, English and Spanish; checked again before it leaves.

Each step reports as it finishes, so the control room's agent panel and audit log show the real
run: what each agent decided, how long it took, and how many tokens it used.

API per Microsoft Learn (2026-10-07): agent_framework.Agent with agent_framework.foundry.
FoundryChatClient; WorkflowBuilder(start_executor=..., output_from=[...]).add_edge(a, b,
condition=...); executors are Executor subclasses with @handler methods.
"""

import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Never, TypeVar

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.foundry import FoundryChatClient
from azure.core.credentials import TokenCredential
from azure.identity import AzureCliCredential, ManagedIdentityCredential
from pydantic import BaseModel

from app.agents.brief import MomentBrief
from app.agents.checker import check_draft, check_localized
from app.agents.schemas import Draft, Interpretation, Localized, Placement

MAX_DRAFTS = 3
PROMPT_VERSION = "v3"  # bump when prompts change, so cached runs are regenerated

Reporter = Callable[[str, str, str], None]  # (agent, action, detail)
T = TypeVar("T", bound=BaseModel)

INTERPRETER = """You are the Interpreter on a live football broadcast team. The match is fictional.
You get a detected moment, the events behind it, the lead-up, the score, and stats.
Decide whether it deserves a graphic right now, and find its angle: one sentence on why it
matters in this match. Most detected moments do; say no only if a viewer would not care.
Choose the graphic type: narrative_line (a story beat), tactical_insight (how or why the teams
are playing this way), stat_graphic (the numbers are the story), player_tag (about one player).
Use only facts from the brief."""

EXPLAINER = """You are the Explainer on a live football broadcast team. The match is fictional.
Write one broadcast graphic for the moment, in English:
- headline: at most 8 words.
- body: at most 30 words, what happened and why it matters.
- claims: every factual statement the graphic makes, each citing the ids of the events in the
  brief that prove it.
Rules: use only numbers, names, and facts that appear in the brief, and never invent a statistic.
Cite only event ids listed in the brief. Background (tactics) may explain why, but it is never a
claim. Present tense, broadcast tone, no exclamation marks. Headlines in sentence case, with
names (players, clubs) capitalized as in the brief."""

PRODUCER = """You are the Producer on a live football broadcast team. A graphic is ready.
Decide how it goes into the queue the human producer works from:
- priority from 0 to 1: how much it matters now, compared with what is already queued;
- shelf_life_seconds from 20 to 90: how long it stays relevant;
- type: keep the proposed type unless another fits better.
Learn from the producer's recent decisions: favour what they approve, play down what they
reject. Give one short reason."""

LOCALIZER = """You are the Localizer on a live football broadcast team. Rewrite a graphic for
two audiences in two languages:
- analyst: precise and tactical, keeps every number and term (xG, field tilt);
- casual: plain and lively, fewer numbers, and no jargon at all: say "better chances" not
  "xG", "pinned them back" not "field tilt";
- English and natural, neutral Spanish: translate football terms ("dominio territorial", not
  "field tilt"), decimals with a comma (0,39).
Keep every name and every number you use exactly as given; do not add facts.
Headlines in sentence case, with names capitalized as given. Headlines at most 8 words, bodies at
most 30 words."""


@dataclass
class Run:
    """Everything one moment's run has produced so far; it travels through the workflow."""

    brief: MomentBrief
    interpretation: Interpretation | None = None
    draft: Draft | None = None
    problems: list[str] = field(default_factory=list)
    drafts: int = 0
    placement: Placement | None = None
    localized: Localized | None = None
    tokens: int = 0


@dataclass
class Outcome:
    status: Literal["proposed", "passed", "failed_checks"]
    run: Run


class AgentTeam:
    """The agents and the client they share. One workflow is built per run."""

    def __init__(self, project_endpoint: str, model: str, credential: TokenCredential) -> None:
        self.client = FoundryChatClient(
            project_endpoint=project_endpoint, model=model, credential=credential
        )
        self.model = model

    @classmethod
    def from_env(cls) -> "AgentTeam":
        # In Azure (Container Apps) the backend has a managed identity; locally, `az login`.
        credential: TokenCredential = (
            ManagedIdentityCredential(client_id=os.environ.get("AZURE_CLIENT_ID"))
            if os.environ.get("IDENTITY_ENDPOINT")
            else AzureCliCredential()
        )
        return cls(os.environ["FOUNDRY_PROJECT_ENDPOINT"], os.environ["FOUNDRY_MODEL"], credential)

    async def ask(
        self, name: str, instructions: str, prompt: str, schema: type[T]
    ) -> tuple[T, int]:
        """One structured call. A separate Agent per call keeps concurrent runs independent."""
        agent = Agent(client=self.client, name=name, instructions=instructions)
        response = await agent.run(prompt, options={"response_format": schema})
        value = response.value
        if not isinstance(value, schema):
            raise ValueError(f"{name} returned no valid {schema.__name__}")
        usage = response.usage_details or {}
        return value, int(usage.get("total_token_count") or 0)

    async def run(self, brief: MomentBrief, report: Reporter) -> Outcome:
        interpreter = _Interpreter(self, report)
        explainer = _Explainer(self, report)
        checker = _Checker(report)
        producer = _Producer(self, report)
        localizer = _Localizer(self, report)
        passed = _End("passed")
        failed = _End("failed_checks")
        workflow = (
            WorkflowBuilder(
                start_executor=interpreter,
                output_from=[localizer, passed, failed],
                name="match-desk-moment",
            )
            .add_edge(interpreter, explainer, condition=_worth_airing)
            .add_edge(interpreter, passed, condition=lambda run: not _worth_airing(run))
            .add_edge(explainer, checker)
            .add_edge(checker, producer, condition=lambda run: not run.problems)
            .add_edge(checker, explainer, condition=_redraft)
            .add_edge(
                checker, failed, condition=lambda run: bool(run.problems) and not _redraft(run)
            )
            .add_edge(producer, localizer)
            .build()
        )
        result = await workflow.run(Run(brief))
        outputs = [o for o in result.get_outputs() if isinstance(o, Outcome)]
        if not outputs:
            raise RuntimeError("the workflow finished without an outcome")
        return outputs[-1]


def _worth_airing(run: Run) -> bool:
    return bool(run.interpretation and run.interpretation.worth_airing)


def _redraft(run: Run) -> bool:
    return bool(run.problems) and run.drafts < MAX_DRAFTS


def _seconds(start: float) -> str:
    return f"{time.perf_counter() - start:.1f} s"


class _Interpreter(Executor):
    def __init__(self, team: AgentTeam, report: Reporter) -> None:
        super().__init__(id="interpreter")
        self.team, self.report = team, report

    @handler
    async def handle(self, run: Run, ctx: WorkflowContext[Run]) -> None:
        start = time.perf_counter()
        prompt = f"{run.brief.text()}\n\nIs this worth a graphic now? What is its angle?"
        run.interpretation, tokens = await self.team.ask(
            "Interpreter", INTERPRETER, prompt, Interpretation
        )
        run.tokens += tokens
        verdict = "Angle" if run.interpretation.worth_airing else "Passed"
        self.report(
            "interpreter",
            "handoff",
            f"{verdict}: {run.interpretation.angle} ({_seconds(start)}, {tokens} tokens)",
        )
        await ctx.send_message(run)


class _Explainer(Executor):
    def __init__(self, team: AgentTeam, report: Reporter) -> None:
        super().__init__(id="explainer")
        self.team, self.report = team, report

    @handler
    async def handle(self, run: Run, ctx: WorkflowContext[Run]) -> None:
        start = time.perf_counter()
        assert run.interpretation
        prompt = (
            f"{run.brief.text()}\n\nANGLE: {run.interpretation.angle}\n"
            f"GRAPHIC TYPE: {run.interpretation.type}"
        )
        if run.problems and run.draft:
            fixes = "\n".join(f"- {p}" for p in run.problems)
            prompt += (
                f"\n\nThe checker rejected your previous draft:\n{run.draft.model_dump_json()}\n"
                f"Problems:\n{fixes}\nFix every problem."
            )
        run.draft, tokens = await self.team.ask("Explainer", EXPLAINER, prompt, Draft)
        run.drafts += 1
        run.tokens += tokens
        cited = len({i for claim in run.draft.claims for i in claim.evidence_event_ids})
        self.report(
            "explainer",
            "handoff",
            f'Draft {run.drafts}: "{run.draft.headline}", {len(run.draft.claims)} claims citing '
            f"{cited} events ({_seconds(start)}, {tokens} tokens)",
        )
        await ctx.send_message(run)


class _Checker(Executor):
    """Code, not a model: holds the draft to the brief."""

    def __init__(self, report: Reporter) -> None:
        super().__init__(id="checker")
        self.report = report

    @handler
    async def handle(self, run: Run, ctx: WorkflowContext[Run]) -> None:
        assert run.draft
        run.problems = check_draft(run.draft, run.brief)
        if run.problems:
            more = f" (+{len(run.problems) - 1} more)" if len(run.problems) > 1 else ""
            then = "sent back to the Explainer" if _redraft(run) else "no drafts left"
            self.report(
                "checker",
                "agent_failure",
                f"Draft {run.drafts} rejected: {run.problems[0]}{more}; {then}",
            )
        else:
            cited = len({i for claim in run.draft.claims for i in claim.evidence_event_ids})
            self.report(
                "checker",
                "handoff",
                f"Verified {len(run.draft.claims)} claims against {cited} cited events",
            )
        await ctx.send_message(run)


class _Producer(Executor):
    def __init__(self, team: AgentTeam, report: Reporter) -> None:
        super().__init__(id="producer")
        self.team, self.report = team, report

    @handler
    async def handle(self, run: Run, ctx: WorkflowContext[Run]) -> None:
        start = time.perf_counter()
        assert run.draft and run.interpretation
        prompt = (
            f"MOMENT: {run.brief.label} ({run.brief.situation})\n"
            f"PROPOSED TYPE: {run.interpretation.type}\n"
            f"GRAPHIC: {run.draft.headline} | {run.draft.body}\n\n"
            f"{run.brief.queue or 'QUEUE: empty. No decisions yet.'}"
        )
        run.placement, tokens = await self.team.ask("Producer", PRODUCER, prompt, Placement)
        run.tokens += tokens
        p = run.placement
        self.report(
            "producer",
            "handoff",
            f"Priority {p.priority:.2f}, {p.shelf_life_seconds} s on the shelf: {p.reason} "
            f"({_seconds(start)}, {tokens} tokens)",
        )
        await ctx.send_message(run)


class _Localizer(Executor):
    def __init__(self, team: AgentTeam, report: Reporter) -> None:
        super().__init__(id="localizer")
        self.team, self.report = team, report

    @handler
    async def handle(self, run: Run, ctx: WorkflowContext[Never, Outcome]) -> None:
        start = time.perf_counter()
        assert run.draft
        prompt = (
            f"HEADLINE: {run.draft.headline}\nBODY: {run.draft.body}\n"
            f"FACTS YOU MAY USE: {'; '.join(c.text for c in run.draft.claims)}"
        )
        run.localized, tokens = await self.team.ask("Localizer", LOCALIZER, prompt, Localized)
        run.tokens += tokens
        problems = check_localized(run.localized, run.brief)
        if problems:
            self.report("localizer", "agent_failure", f"Variants rejected: {problems[0]}; retrying")
            fixes = "\n".join(f"- {p}" for p in problems)
            run.localized, retry_tokens = await self.team.ask(
                "Localizer", LOCALIZER, f"{prompt}\n\nFix these problems:\n{fixes}", Localized
            )
            run.tokens += retry_tokens
            if check_localized(run.localized, run.brief):
                run.localized = None  # the desk uses the English draft for every variant
                self.report("localizer", "agent_failure", "Variants failed twice; English used")
            else:
                self.report("localizer", "retry", "Retry passed: 4 variants written")
        else:
            self.report(
                "localizer",
                "handoff",
                f"Wrote 4 variants: analyst and casual, EN and ES "
                f"({_seconds(start)}, {tokens} tokens)",
            )
        await ctx.yield_output(Outcome("proposed", run))


class _End(Executor):
    def __init__(self, status: Literal["passed", "failed_checks"]) -> None:
        super().__init__(id=status)
        self.status = status

    @handler
    async def handle(self, run: Run, ctx: WorkflowContext[Never, Outcome]) -> None:
        await ctx.yield_output(Outcome(self.status, run))
