"""The agent team, as a Microsoft Agent Framework workflow on Microsoft Foundry.

One run per moment:

    Interpreter ─▶ Explainer ─▶ Checker ─▶ Fact-checker ─▶ Producer ─▶ Localizer ─▶ proposal
         │             ▲           │            │
         │             └───────────┴────────────┤ problems: back to the Explainer (3 drafts)
         ▼                                      ▼
      passed                     failed checks (the desk falls back to its scripted copy)

- Interpreter (model): is the moment worth a graphic now, and what is its angle?
- Explainer (model): headline, body, and claims, each citing the events that prove it. It can
  look up club tactics, the laws, and what metrics mean in the knowledge base (Azure AI Search,
  Foundry IQ) through its MCP endpoint: once per moment, because every lookup costs another
  model round trip that resends the whole prompt. A redraft reuses what the first draft found.
- Checker (code): every id, number, and name against the brief. A model checking its own work
  tends to agree with itself; this doesn't.
- Fact-checker (model): what the graphic says against what the brief shows: who did what to
  whom, which club leads or has the ball, the order of events. The code can't see the right
  names and numbers in the wrong relation; a separate reader, with no stake in the draft, can.
  Foundry's evaluation found exactly those errors getting through (docs/evals/graphics.md).
- Producer (model): priority and shelf life, given the live queue and what this producer has
  approved and rejected.
- Localizer (model): analyst and casual, English and Spanish; checked again before it leaves.

Each step reports as it finishes, so the control room's agent panel and audit log show the real
run: what each agent decided, how long it took, and how many tokens it used.

API per Microsoft Learn (2026-10-07): agent_framework.Agent with agent_framework.foundry.
FoundryChatClient; WorkflowBuilder(start_executor=..., output_from=[...]).add_edge(a, b,
condition=...); executors are Executor subclasses with @handler methods.
"""

import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Literal, Never, TypeVar

from agent_framework import (
    Agent,
    Executor,
    MCPStreamableHTTPTool,
    WorkflowBuilder,
    WorkflowContext,
    handler,
)
from agent_framework.foundry import FoundryChatClient
from azure.core.credentials import TokenCredential
from azure.identity import AzureCliCredential, ManagedIdentityCredential
from pydantic import BaseModel

from app.agents.brief import MomentBrief
from app.agents.checker import check_draft, check_localized
from app.agents.schemas import Draft, FactCheck, Interpretation, Localized, Placement

MAX_DRAFTS = 3
PROMPT_VERSION = "v8"  # bump when prompts change, so cached runs are regenerated
KNOWLEDGE_BASE = "matchdesk-kb"  # app/rag/knowledge_base.py builds it
KNOWLEDGE_MCP_API = "2026-08-01-preview"  # the knowledge base MCP endpoint is in preview
SEARCH_SCOPE = "https://search.azure.com/.default"

log = logging.getLogger(__name__)

Reporter = Callable[[str, str, str], None]  # (agent, action, detail)
T = TypeVar("T", bound=BaseModel)

INTERPRETER = """You are the Interpreter on a live football broadcast team. The match is fictional.
You get a detected moment, the events behind it, the lead-up, the score, and stats.
Decide whether it deserves a graphic right now, and find its angle: one sentence on why it
matters in this match. Most detected moments do; say no only if a viewer would not care.
Choose the graphic type: narrative_line (a story beat), tactical_insight (how or why the teams
are playing this way), stat_graphic (the numbers are the story), player_tag (about one player).
Base the angle only on the brief, and list the ids of the events it rests on. Get the basics
right: which club leads, which club is ahead on each stat (the brief's Ahead line), and the order
events happened in."""

EXPLAINER = """You are the Explainer on a live football broadcast team. The match is fictional.
Write one broadcast graphic for the moment, in English:
- headline: at most 8 words.
- body: at most 30 words, what happened and why it matters in this match.
- claims: every factual statement the graphic makes, each citing the ids of the events in the
  brief that prove it.
Rules: use only numbers, names, and facts that appear in the brief, and never invent a statistic.
Cite only event ids listed in the brief. The ANGLE is the Interpreter's suggestion: if it
disagrees with the brief, follow the brief.
Why it matters comes only from the brief: the score and who leads, the stats (the Ahead line says
which club is ahead on each), and the events. Don't guess at what a team or player intends
(protecting a lead, a like-for-like change), at a player's position or role, or at a style of
play: the background says how a club usually plays, not what happened in this moment. When the
brief shows no more than the event itself, say what happened plainly, with the score. Get the
details right: which club leads, which club has more of the ball, the order events happened in,
who passed to whom and whether it arrived, and whether this is a club's first offside or booking.
The score, the minute, and the stats so far are context:
the body may mention them, but they are not claims, so don't list them. PLAYER STORIES (the
Golden Boot race, a milestone, a player against his old club) are context too: use one when the
moment is about that player, word for word with its numbers, never as a claim.
When the angle turns on how a club plays, the laws (offside, restarts), or what a metric means
(xG, field tilt, momentum), first look it up with knowledge_base_retrieve, and list the titles of
the sections you used in background_used. You get one lookup per moment: make a single call, with
a query variant for each thing you need. Background explains why; it is never a claim, and its
numbers (tactical dials) never appear in the graphic.
Present tense, broadcast tone, no exclamation marks. Headlines in sentence case, with names
(players, clubs) capitalized as in the brief."""

FACT_CHECKER = """You are the fact-checker on a live football broadcast team. The match is
fictional. You get the brief and a graphic's headline and body. Split them into statements and
give each a verdict against the brief, the way a careful editor would:
- supported: the brief states it.
- fair reading: it follows directly from the brief's events, score, or stats. "Northgate have the
  better chances" when their xG is higher; "after a quick passing move" when the lead-up shows
  one; a player story quoted as it is.
- unsupported: the brief doesn't show it. History it doesn't record ("again", "first", "another"
  need the earlier events in the brief); what a team or player intends (protecting a lead); a
  player's position or role; a style of play presented as what happened in this moment (the
  background says how a club usually plays).
- wrong: the brief shows otherwise. The wrong club, side, score, or leader; which club has more
  of the ball or the territory (the brief's Ahead line); the wrong order of events or minute; who
  did what to whom (a misplaced pass did not reach its man; a block, a save, and a goal differ).
Judge what the words say, not how they are phrased: don't mark tone or word choice."""

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
    rejected_by: str = "checker"  # which check the problems come from
    drafts: int = 0
    placement: Placement | None = None
    localized: Localized | None = None
    tokens: int = 0
    background: str = ""  # what the Explainer's lookup returned, reused on redrafts


@dataclass
class Outcome:
    status: Literal["proposed", "passed", "failed_checks"]
    run: Run


class AgentTeam:
    """The agents and the client they share. One workflow is built per run."""

    def __init__(
        self,
        project_endpoint: str,
        model: str,
        credential: TokenCredential,
        search_endpoint: str | None = None,
    ) -> None:
        self.client = FoundryChatClient(
            project_endpoint=project_endpoint, model=model, credential=credential
        )
        self.model = model
        # One tool call per request; then the model must answer (agent_framework/_tools.py,
        # FunctionInvocationConfiguration). The knowledge base is the only tool.
        self.client.function_invocation_configuration["max_function_calls"] = 1
        self.knowledge: MCPStreamableHTTPTool | None = None
        if search_endpoint:

            def headers(_: dict[str, object]) -> dict[str, str]:
                return {"Authorization": f"Bearer {credential.get_token(SEARCH_SCOPE).token}"}

            self.knowledge = MCPStreamableHTTPTool(
                name="knowledge",
                url=f"{search_endpoint}/knowledgebases/{KNOWLEDGE_BASE}/mcp"
                f"?api-version={KNOWLEDGE_MCP_API}",
                header_provider=headers,
                allowed_tools=["knowledge_base_retrieve"],
                load_prompts=False,
                approval_mode="never_require",
            )

    async def connect(self) -> None:
        """Connect to the knowledge base's MCP endpoint; without it the Explainer still works."""
        if not self.knowledge:
            return
        try:
            await self.knowledge.connect()
        except Exception as error:
            log.warning("knowledge base unavailable, Explainer runs without it: %s", error)
            self.knowledge = None

    async def close(self) -> None:
        if self.knowledge:
            await self.knowledge.close()

    @classmethod
    def from_env(cls, model_env: str = "FOUNDRY_MODEL", knowledge: bool = True) -> "AgentTeam":
        """A team on the deployment named by `model_env` (FOUNDRY_MODEL, or the Watchers'
        FOUNDRY_WATCHER_MODEL, falling back to FOUNDRY_MODEL)."""
        # In Azure (Container Apps) the backend has a managed identity; locally, `az login`.
        credential: TokenCredential = (
            ManagedIdentityCredential(client_id=os.environ.get("AZURE_CLIENT_ID"))
            if os.environ.get("IDENTITY_ENDPOINT")
            else AzureCliCredential()
        )
        return cls(
            os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            os.environ.get(model_env) or os.environ["FOUNDRY_MODEL"],
            credential,
            search_endpoint=os.environ.get("AZURE_SEARCH_ENDPOINT") if knowledge else None,
        )

    async def ask(
        self, name: str, instructions: str, prompt: str, schema: type[T]
    ) -> tuple[T, int]:
        """One structured call. A separate Agent per call keeps concurrent runs independent."""
        value, tokens, _ = await self.ask_with_tools(name, instructions, prompt, schema, None)
        return value, tokens

    async def ask_with_tools(
        self,
        name: str,
        instructions: str,
        prompt: str,
        schema: type[T],
        tools: list[MCPStreamableHTTPTool] | None,
    ) -> tuple[T, int, list[str]]:
        """A structured call that may use tools; also returns what the tools gave back."""
        # A stable id per role (each call gets its own Agent), so traces group by agent.
        agent = Agent(
            client=self.client,
            id=f"tiki-taka-{name.lower()}",
            name=name,
            instructions=instructions,
            tools=tools,
        )
        response = await agent.run(prompt, options={"response_format": schema})
        value = response.value
        if not isinstance(value, schema):
            raise ValueError(f"{name} returned no valid {schema.__name__}")
        usage = response.usage_details or {}
        results = [
            content.result
            for message in response.messages
            for content in message.contents
            if content.type == "function_result" and content.result
        ]
        return value, int(usage.get("total_token_count") or 0), results

    async def run(self, brief: MomentBrief, report: Reporter) -> Outcome:
        interpreter = _Interpreter(self, report)
        explainer = _Explainer(self, report)
        checker = _Checker(report)
        fact_checker = _FactChecker(self, report)
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
            .add_edge(checker, fact_checker, condition=lambda run: not run.problems)
            .add_edge(checker, explainer, condition=_redraft)
            .add_edge(checker, failed, condition=_out_of_drafts)
            .add_edge(fact_checker, producer, condition=lambda run: not run.problems)
            .add_edge(fact_checker, explainer, condition=_redraft)
            .add_edge(fact_checker, failed, condition=_out_of_drafts)
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


def _own(run: Run) -> Run:
    """A copy for this step to change. The workflow sends a message down all of a step's edges at
    once, and each edge tests its condition and then runs its target: a step that changed the Run
    it was sent could change the condition a sibling edge has yet to test (the fact-checker's
    problems would send the checker's message back to the Explainer too). So no step does."""
    return replace(run)


def _redraft(run: Run) -> bool:
    return bool(run.problems) and run.drafts < MAX_DRAFTS


def _out_of_drafts(run: Run) -> bool:
    return bool(run.problems) and not _redraft(run)


def _seconds(start: float) -> str:
    return f"{time.perf_counter() - start:.1f} s"


class _Interpreter(Executor):
    def __init__(self, team: AgentTeam, report: Reporter) -> None:
        super().__init__(id="interpreter")
        self.team, self.report = team, report

    @handler
    async def handle(self, run: Run, ctx: WorkflowContext[Run]) -> None:
        run = _own(run)
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
        run = _own(run)
        start = time.perf_counter()
        assert run.interpretation
        prompt = (
            f"{run.brief.text()}\n\nANGLE (the Interpreter's suggestion): "
            f"{run.interpretation.angle}\nGRAPHIC TYPE: {run.interpretation.type}"
        )
        if run.problems and run.draft:
            fixes = "\n".join(f"- {p}" for p in run.problems)
            if run.background:
                prompt += (
                    "\n\nWHAT YOUR LOOKUP FOUND (there is no second lookup):\n" + run.background
                )
            prompt += (
                f"\n\nThe {run.rejected_by} sent your previous draft back:\n"
                f"{run.draft.model_dump_json()}\nProblems:\n{fixes}\nFix every problem: "
                "correct what is wrong, and cut what the brief doesn't show rather than "
                "rephrasing it. A plain graphic that is all true beats a vivid one that isn't."
            )
        # The lookup is for the first draft only; a redraft fixes citations, not background.
        first = run.drafts == 0
        knowledge = [self.team.knowledge] if self.team.knowledge and first else None
        run.draft, tokens, found = await self.team.ask_with_tools(
            "Explainer", EXPLAINER, prompt, Draft, knowledge
        )
        if first:
            run.background = "\n".join(found)
        run.drafts += 1
        run.tokens += tokens
        cited = len({i for claim in run.draft.claims for i in claim.evidence_event_ids})
        used = run.draft.background_used if first and run.background else []
        pages = dict.fromkeys(title.split(":")[0] for title in used)
        looked_up = f"; looked up {', '.join(pages)}" if pages else ""
        self.report(
            "explainer",
            "handoff",
            f'Draft {run.drafts}: "{run.draft.headline}", {len(run.draft.claims)} claims citing '
            f"{cited} events{looked_up} ({_seconds(start)}, {tokens} tokens)",
        )
        await ctx.send_message(run)


class _Checker(Executor):
    """Code, not a model: holds the draft to the brief."""

    def __init__(self, report: Reporter) -> None:
        super().__init__(id="checker")
        self.report = report

    @handler
    async def handle(self, run: Run, ctx: WorkflowContext[Run]) -> None:
        run = _own(run)
        assert run.draft
        run.problems = check_draft(run.draft, run.brief)
        run.rejected_by = "checker"
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


class _FactChecker(Executor):
    """A model, after the code: does the graphic say what the brief shows?"""

    def __init__(self, team: AgentTeam, report: Reporter) -> None:
        super().__init__(id="fact_checker")
        self.team, self.report = team, report

    @handler
    async def handle(self, run: Run, ctx: WorkflowContext[Run]) -> None:
        run = _own(run)
        start = time.perf_counter()
        assert run.draft
        prompt = (
            f"{run.brief.text()}\n\nTHE GRAPHIC\nHEADLINE: {run.draft.headline}\n"
            f"BODY: {run.draft.body}"
        )
        verdict, tokens = await self.team.ask("Fact-checker", FACT_CHECKER, prompt, FactCheck)
        run.tokens += tokens
        run.problems = verdict.problems
        run.rejected_by = "fact-checker"
        if run.problems:
            more = f" (+{len(run.problems) - 1} more)" if len(run.problems) > 1 else ""
            then = "sent back to the Explainer" if _redraft(run) else "no drafts left"
            self.report(
                "fact_checker",
                "agent_failure",
                f"Draft {run.drafts} doesn't match the brief: {run.problems[0]}{more}; {then}",
            )
        else:
            self.report(
                "fact_checker",
                "handoff",
                f"All {len(verdict.statements)} statements match the brief "
                f"({_seconds(start)}, {tokens} tokens)",
            )
        await ctx.send_message(run)


class _Producer(Executor):
    def __init__(self, team: AgentTeam, report: Reporter) -> None:
        super().__init__(id="producer")
        self.team, self.report = team, report

    @handler
    async def handle(self, run: Run, ctx: WorkflowContext[Run]) -> None:
        run = _own(run)
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
        run = _own(run)
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
