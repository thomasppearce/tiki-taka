"""The agent team's guardrails and wiring: the citation checker, and the desk working with the
runner (a fake team stands in for Foundry, so no test calls a model)."""

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from app.agents.brief import MomentBrief, build_brief, numbers_in
from app.agents.checker import check_draft
from app.agents.runner import AgentRunner
from app.agents.schemas import Draft, DraftClaim, Interpretation, Localized, Placement
from app.agents.team import AgentTeam, Outcome, Run
from app.live.desk import AGENT_DEADLINE_MS, ProposalDesk
from app.live.service import MatchdayService
from app.state.aggregator import key_moments

FEATURED = "m_l1_1"


def featured_desk(service: MatchdayService, agents: Any) -> ProposalDesk:
    base = service.desks[FEATURED]
    m = base.match
    moments = key_moments(
        m.result.events,
        service.impacts[FEATURED],
        m.home.club_id,
        m.result.full_time_ms,
        service.surname,
        service.short,
    )
    return ProposalDesk(m, moments, base.ctx, autopilot=False, agents=agents)


def goal_brief(service: MatchdayService) -> MomentBrief:
    desk = service.desks[FEATURED]
    c = next(c for c in desk.candidates if c.kind == "goal")
    return build_brief(
        c.moment_id,
        c.kind,
        c.label,
        c.known_ms,
        c.evidence_ids,
        desk.match.result.events,
        desk.ctx,
        desk.match.home,
        desk.match.away,
        c.copy.claims,
    )


# --- The checker -------------------------------------------------------------------------------


def test_the_checker_passes_a_draft_that_sticks_to_the_brief(service: MatchdayService) -> None:
    brief = goal_brief(service)
    goal = next(f for f in brief.evidence if "GOAL" in f.text)
    scorer = goal.players[0]
    draft = Draft(
        headline=f"{scorer} opens the scoring",
        body=f"{scorer} finishes the move.",
        claims=[DraftClaim(text=f"Goal by {scorer}", evidence_event_ids=[goal.event_id])],
    )
    assert check_draft(draft, brief) == []


def test_the_checker_catches_invented_ids_numbers_and_names(service: MatchdayService) -> None:
    brief = goal_brief(service)
    shot = next(f for f in brief.evidence if "shot from" in f.text)
    involved = {name for f in (*brief.evidence, *brief.lead_up) for name in f.players}
    outsider = next(name for name in sorted(brief.surnames) if name not in involved)
    draft = Draft(
        headline=f"{outsider} watches on",
        body="A goal from nowhere.",
        claims=[
            DraftClaim(text="A goal from 47 m", evidence_event_ids=[shot.event_id]),
            DraftClaim(text="The keeper was beaten", evidence_event_ids=["evt_999999"]),
            DraftClaim(text="It counts", evidence_event_ids=[]),
        ],
    )
    problems = " | ".join(check_draft(draft, brief))
    assert "says 47" in problems
    assert "evt_999999" in problems
    assert "cites no events" in problems
    assert f"names {outsider}" in problems


def test_a_claim_may_use_the_figures_code_computed_from_its_events(
    service: MatchdayService,
) -> None:
    desk = service.desks[FEATURED]
    c = next(c for c in desk.candidates if c.kind == "territory")  # labelled "Territory: NGR 72%"
    brief = build_brief(
        c.moment_id,
        c.kind,
        c.label,
        c.known_ms,
        c.evidence_ids,
        desk.match.result.events,
        desk.ctx,
        desk.match.home,
        desk.match.away,
        c.copy.claims,
    )
    share = int(max(numbers_in(c.label)))
    figure = c.copy.claims[0]  # "28 of 39 completed final-third passes from 5' to 15' were NGR's"
    draft = Draft(
        headline="Northgate pin Westmere back",
        body="Northgate are camped in the final third.",
        claims=[
            DraftClaim(
                text=f"{share}% of the final-third passes", evidence_event_ids=c.evidence_ids
            ),
            DraftClaim(text=figure.text, evidence_event_ids=figure.evidence_event_ids[:5]),
        ],
    )
    assert check_draft(draft, brief) == []
    elsewhere = [brief.lead_up[0].event_id]  # the same number, citing a play it didn't come from
    draft.claims[0].evidence_event_ids = elsewhere
    assert any(f"says {share}" in p for p in check_draft(draft, brief))


# --- The desk and the runner -------------------------------------------------------------------


class FakeTeam:
    """Answers like the real team, without a model."""

    model = "fake-model"

    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    async def run(self, brief: MomentBrief, report: Any) -> Outcome:
        self.calls += 1
        if self.fail:
            raise RuntimeError("model unavailable")
        evidence = [f.event_id for f in brief.evidence][:1]
        report("interpreter", "handoff", "Angle: it matters")
        draft = Draft(
            headline="Agent headline",
            body="Agent body.",
            claims=[DraftClaim(text="Agent claim", evidence_event_ids=evidence)],
        )
        report("explainer", "handoff", "Draft 1")
        report("checker", "handoff", "Verified 1 claim")
        report("producer", "handoff", "Priority 0.90")
        report("localizer", "handoff", "Wrote 4 variants")
        run = Run(
            brief,
            interpretation=Interpretation(
                worth_airing=True, angle="It matters", type="stat_graphic"
            ),
            draft=draft,
            placement=Placement(
                priority=0.9, shelf_life_seconds=40, type="stat_graphic", reason="x"
            ),
        )
        return Outcome("proposed", run)


def run_first_moment(service: MatchdayService, team: FakeTeam, cache: Path) -> ProposalDesk:
    async def scenario() -> ProposalDesk:
        runner = AgentRunner(team, cache_dir=cache)  # type: ignore[arg-type]
        runner.start()
        desk = featured_desk(service, runner)
        first = desk.candidates[0]
        desk.sync(0)
        desk.sync(first.known_ms)  # the moment is knowable: the desk briefs the team
        await asyncio.sleep(0)
        assert runner.queue
        await runner.queue.join()
        desk.sync(first.known_ms + 1_000)
        await runner.stop()
        return desk

    return asyncio.run(scenario())


def test_the_agent_team_writes_the_proposal(service: MatchdayService, tmp_path: Path) -> None:
    team = FakeTeam()
    desk = run_first_moment(service, team, tmp_path)
    [proposal] = desk.state.pending
    assert proposal.headline.analyst.en == "Agent headline"
    assert proposal.type == "stat_graphic" and proposal.priority == 0.9
    assert "checker" in proposal.produced_by
    actors = [r.actor for r in reversed(desk.state.audit)]
    assert actors[:6] == [
        "orchestrator",
        "interpreter",
        "explainer",
        "checker",
        "producer",
        "localizer",
    ]
    assert team.calls == 1


def test_later_loops_replay_from_the_cache(service: MatchdayService, tmp_path: Path) -> None:
    team = FakeTeam()
    run_first_moment(service, team, tmp_path)
    desk = run_first_moment(service, team, tmp_path)  # a new runner, the same cache on disk
    assert team.calls == 1
    assert any("cached" in (r.detail or "") for r in desk.state.audit)
    assert desk.state.pending[0].headline.analyst.en == "Agent headline"


def test_a_failed_team_falls_back_to_the_script(service: MatchdayService, tmp_path: Path) -> None:
    desk = run_first_moment(service, FakeTeam(fail=True), tmp_path)
    [proposal] = desk.state.pending
    assert proposal.produced_by == ["orchestrator"]
    assert proposal.headline == desk.candidates[0].copy.headline
    assert any("scripted copy used" in (r.detail or "") for r in desk.state.audit)


def test_no_answer_in_time_falls_back_to_the_script(service: MatchdayService) -> None:
    class Silent:
        def request(self, *args: Any) -> None:
            pass  # never answers

    desk = featured_desk(service, Silent())
    first = desk.candidates[0]
    desk.sync(0)
    desk.sync(first.known_ms)
    assert desk.state.pending == []
    desk.sync(first.known_ms + AGENT_DEADLINE_MS)
    assert [p.produced_by for p in desk.state.pending] == [["orchestrator"]]


def test_a_replayed_brief_still_gets_its_full_time(service: MatchdayService) -> None:
    """When a page connects, the desk replays the last 90 s at once; a moment it briefs the team
    on during that catch-up still gets the full deadline from now, not from the moment."""

    class Silent:
        def request(self, *args: Any) -> None:
            pass

    desk = featured_desk(service, Silent())
    first = desk.candidates[0]
    desk.sync(first.known_ms + 30_000)  # first sync: replays the brief at known_ms
    assert desk.state.awaiting and desk.state.pending == []
    desk.sync(first.known_ms + 30_000 + AGENT_DEADLINE_MS)
    assert [p.produced_by for p in desk.state.pending] == [["orchestrator"]]


# --- The knowledge base ------------------------------------------------------------------------


def test_the_knowledge_corpus_splits_into_sections_without_squad_tables() -> None:
    from app.rag.knowledge_base import sections

    docs = sections()
    assert {d["category"] for d in docs} == {"club", "concept", "laws"}
    assert len({d["id"] for d in docs}) == len(docs)
    assert not any(d["title"].endswith(": Squad") for d in docs)  # the brief lists the players


class ScriptedTeam(AgentTeam):
    """The real workflow, with scripted answers where the model would be."""

    def __init__(self, brief: MomentBrief) -> None:  # no client: nothing reaches Foundry
        self.model = "scripted"
        self.knowledge = cast(Any, "knowledge base")  # stands in for the MCP tool
        self.calls: list[tuple[str, str, bool]] = []
        goal = next(f for f in brief.evidence if "GOAL" in f.text)
        scorer = goal.players[0]
        uncited = DraftClaim(text=f"Goal by {scorer}", evidence_event_ids=[])
        cited = DraftClaim(text=f"Goal by {scorer}", evidence_event_ids=[goal.event_id])
        self.drafts = [
            Draft(headline=f"{scorer} scores", body=f"{scorer} finishes.", claims=[uncited]),
            Draft(headline=f"{scorer} scores", body=f"{scorer} finishes.", claims=[cited]),
        ]
        self.answers: dict[type, Any] = {
            Interpretation: Interpretation(worth_airing=True, angle="x", type="stat_graphic"),
            Placement: Placement(
                priority=0.9, shelf_life_seconds=40, type="stat_graphic", reason="x"
            ),
            Localized: Localized(**{name: f"{scorer} scores" for name in Localized.model_fields}),
        }

    async def ask_with_tools(  # type: ignore[override]
        self, name: str, instructions: str, prompt: str, schema: type, tools: Sequence[Any] | None
    ) -> tuple[Any, int, list[str]]:
        self.calls.append((name, prompt, bool(tools)))
        if schema is Draft:
            found = ["Offside trap: Overview. A high line steps up together."] if tools else []
            return self.drafts.pop(0), 0, found
        return self.answers[schema], 0, []


def test_the_explainer_looks_up_once_and_reuses_it_on_a_redraft(service: MatchdayService) -> None:
    brief = goal_brief(service)
    team = ScriptedTeam(brief)
    outcome = asyncio.run(team.run(brief, lambda *step: None))
    assert outcome.status == "proposed" and outcome.run.drafts == 2
    explainer = [(tools, prompt) for name, prompt, tools in team.calls if name == "Explainer"]
    assert [tools for tools, _ in explainer] == [True, False]  # the redraft gets no tool
    assert "A high line steps up together." in explainer[1][1]  # but sees what was found
