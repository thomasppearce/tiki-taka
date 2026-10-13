"""The graphics team against a single agent, on every moment of the featured match, judged on
Microsoft Foundry.

    uv run python -m app.evals.graphics             # all of the featured match's moments
    uv run python -m app.evals.graphics --limit 5   # a quick look

Each moment the desk detects in the featured match becomes the same brief for both: the team
(app/agents/team.py) and the single-agent baseline (solo.py, same model, tools, and
instructions). Then:
- the team's checker (code) holds each answer to its brief: could it air with its receipts?
- Foundry's built-in evaluators judge what each would put on air, the English headline and body,
  against the brief: groundedness (is everything in it supported by the brief), relevance, and
  coherence. The judge is a different model from the writers (FOUNDRY_WATCHER_MODEL), so neither
  side is marked by its own model.

Writes docs/evals/graphics.json (every answer, check, and score) and docs/evals/graphics.md (the
summary). The two runs are in the Foundry portal under Evaluations.

API per the installed agent-framework-foundry 1.14.0: FoundryEvals(client, model, evaluators)
.evaluate(items, eval_name) returns EvalResults (eval_id, run_id, report_url); per-item scores
come from the OpenAI Evals API (evals.runs.output_items.list) on the same project.
"""

import argparse
import asyncio
import json
import os
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from agent_framework import EvalItem, Message
from agent_framework.foundry import FoundryEvals
from dotenv import load_dotenv

from app.agents.brief import MomentBrief, build_brief
from app.agents.team import AgentTeam
from app.agents.tracing import start_tracing
from app.evals.solo import run_solo
from app.live.service import MatchdayService

OUT = Path(__file__).resolve().parents[3] / "docs" / "evals"
EVALUATORS = [FoundryEvals.GROUNDEDNESS, FoundryEvals.RELEVANCE, FoundryEvals.COHERENCE]
CONCURRENCY = 3  # runs at once, within the deployment's tokens-per-minute quota
TIMEOUT_S = 120.0

System = Literal["team", "solo"]


@dataclass
class Answer:
    """What one system did with one moment."""

    system: System
    moment_id: str
    minute: int
    kind: str
    label: str
    airs: bool = False  # it puts a graphic on air
    passed_on: bool = False  # it judged the moment not worth a graphic
    headline: str = ""
    body: str = ""
    claims: list[dict[str, Any]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # the checker's, on the last draft
    first_draft_ok: bool | None = None  # team only: did the first draft pass both checks
    sent_back: dict[str, int] = field(
        default_factory=dict
    )  # team only: drafts each check sent back
    drafts: int = 0
    tokens: int = 0
    seconds: float = 0.0
    error: str | None = None
    background: str = ""  # what its knowledge-base lookup found: the judge sees it too
    scores: dict[str, float] = field(default_factory=dict)  # Foundry's, on what airs
    passes: dict[str, bool] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)  # the judge's, in its words

    @property
    def clean(self) -> bool:
        """On air with every claim, number, and name checked against the brief."""
        return self.airs and not self.problems


def briefs(service: MatchdayService) -> list[tuple[Any, MomentBrief]]:
    """Every moment the featured match's desk asks the agents about, as the brief they get."""
    match = next(m for m in service.matches if m.featured)
    desk = service.desks[match.match_id]
    return [
        (
            c,
            build_brief(
                c.moment_id,
                c.kind,
                c.label,
                c.known_ms,
                c.evidence_ids,
                match.result.events,
                desk.ctx,
                match.home,
                match.away,
                c.copy.claims,
                service.stories(match.match_id, c.known_ms),
            ),
        )
        for c in desk.candidates
    ]


async def run_team(team: AgentTeam, candidate: Any, brief: MomentBrief) -> Answer:
    answer = _answer("team", candidate)

    def report(agent: str, action: str, detail: str) -> None:
        if agent in ("checker", "fact_checker") and action == "agent_failure":
            answer.sent_back[agent] = answer.sent_back.get(agent, 0) + 1

    start = time.perf_counter()
    try:
        outcome = await asyncio.wait_for(team.run(brief, report), TIMEOUT_S)
    except Exception as error:
        answer.error = "timed out" if isinstance(error, TimeoutError) else repr(error)
        return answer
    run = outcome.run
    answer.seconds, answer.tokens, answer.drafts = (
        time.perf_counter() - start,
        run.tokens,
        run.drafts,
    )
    answer.passed_on = outcome.status == "passed"
    answer.airs = outcome.status == "proposed"
    answer.first_draft_ok = None if answer.passed_on else answer.airs and run.drafts == 1
    answer.problems = list(run.problems)
    answer.background = run.background
    if run.draft:
        answer.headline, answer.body = run.draft.headline, run.draft.body
        answer.claims = [c.model_dump() for c in run.draft.claims]
    return answer


async def run_single(team: AgentTeam, candidate: Any, brief: MomentBrief) -> Answer:
    answer = _answer("solo", candidate)
    start = time.perf_counter()
    try:
        graphic, tokens, problems, found = await asyncio.wait_for(run_solo(team, brief), TIMEOUT_S)
    except Exception as error:
        answer.error = "timed out" if isinstance(error, TimeoutError) else repr(error)
        return answer
    answer.seconds, answer.tokens, answer.drafts = time.perf_counter() - start, tokens, 1
    answer.passed_on = not graphic.worth_airing
    answer.airs = graphic.worth_airing  # nobody checks it: what it writes goes to the queue
    answer.problems = problems if answer.airs else []
    answer.headline, answer.body = graphic.headline, graphic.body
    answer.claims = [c.model_dump() for c in graphic.claims]
    answer.background = found
    return answer


def _context(brief: str, background: str) -> str:
    """What the writer had to go on: the brief, and whatever its lookup found."""
    if not background:
        return brief
    return f"{brief}\n\nFROM THE KNOWLEDGE BASE (looked up for this moment):\n{background}"


def _answer(system: System, candidate: Any) -> Answer:
    return Answer(
        system=system,
        moment_id=candidate.moment_id,
        minute=candidate.known_ms // 60_000 + 1,
        kind=candidate.kind,
        label=candidate.label,
    )


async def judge(
    team: AgentTeam, judge_model: str, answers: list[Answer], texts: dict[str, str], name: str
) -> str:
    """Foundry's evaluators on what airs; scores go back onto the answers. Returns the report
    URL in the Foundry portal."""
    airing = [a for a in answers if a.airs]
    if not airing:
        return ""
    items = [
        EvalItem(
            conversation=[
                Message("user", [texts[a.moment_id]]),
                Message("assistant", [f"{a.headline}\n{a.body}"]),
            ],
            context=_context(texts[a.moment_id], a.background),
        )
        for a in airing
    ]
    evals = FoundryEvals(
        client=team.client, model=judge_model, evaluators=EVALUATORS, timeout=1200.0
    )
    results = await evals.evaluate(items, eval_name=name)
    by_text = {(texts[a.moment_id], f"{a.headline}\n{a.body}"): a for a in airing}
    openai = team.client.client
    page = await openai.evals.runs.output_items.list(run_id=results.run_id, eval_id=results.eval_id)
    async for output in page:
        item = output.datasource_item or {}
        answer = by_text.get((item.get("query"), item.get("response")))
        if answer is None:
            continue
        for result in output.results or []:
            short = result.name.removeprefix("builtin.")
            answer.scores[short] = float(result.score)
            answer.passes[short] = bool(result.passed)
            answer.reasons[short] = str(getattr(result, "reason", "") or "")
    return results.report_url or ""


async def main(limit: int | None) -> None:
    load_dotenv()
    service = MatchdayService()
    moments = briefs(service)[:limit]
    texts = {c.moment_id: brief.text() for c, brief in moments}
    team = AgentTeam.from_env()
    await start_tracing(team.client)  # the eval's runs are traced like live ones
    await team.connect()
    judge_model = os.environ.get("FOUNDRY_WATCHER_MODEL") or team.model
    gate = asyncio.Semaphore(CONCURRENCY)

    async def gated(run: Any, candidate: Any, brief: MomentBrief) -> Answer:
        async with gate:
            answer: Answer = await run(team, candidate, brief)
        outcome = answer.error or ("airs" if answer.airs else "doesn't air")
        flags = f", {len(answer.problems)} problems" if answer.problems else ""
        print(
            f"{answer.system:>4} {answer.minute:>3}' {answer.label}: {outcome}{flags}", flush=True
        )
        return answer

    print(f"{len(moments)} moments, team and single agent, {CONCURRENCY} at a time")
    answers = await asyncio.gather(
        *(gated(run, c, b) for c, b in moments for run in (run_team, run_single))
    )
    team_answers = [a for a in answers if a.system == "team"]
    solo_answers = [a for a in answers if a.system == "solo"]
    print("judging on Foundry")
    reports = {
        "team": await judge(team, judge_model, team_answers, texts, "Tiki-Taka graphics team"),
        "solo": await judge(team, judge_model, solo_answers, texts, "Tiki-Taka single agent"),
    }
    await team.close()

    OUT.mkdir(parents=True, exist_ok=True)
    meta = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "matchday": service.fingerprint,
        "writer_model": os.environ.get("FOUNDRY_MODEL_LABEL", team.model),
        "judge_model": judge_model,
        "evaluators": EVALUATORS,
        "reports": reports,
    }
    payload = {**meta, "answers": [asdict(a) for a in answers]}
    (OUT / "graphics.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    summary = render(meta, team_answers, solo_answers)
    (OUT / "graphics.md").write_text(summary)
    print(summary)


def render(meta: dict[str, Any], team: list[Answer], solo: list[Answer]) -> str:
    """The summary page: the headline numbers, then every moment side by side."""

    def share(part: int, whole: int) -> str:
        return f"{part}/{whole} ({part / whole:.0%})" if whole else "0/0"

    def mean_score(answers: list[Answer], name: str) -> str:
        scores = [a.scores[name] for a in answers if name in a.scores]
        passed = sum(a.passes.get(name, False) for a in answers if name in a.passes)
        if not scores:
            return "n/a"
        return f"{statistics.mean(scores):.2f} ({passed}/{len(scores)} pass)"

    def row(label: str, value: Any) -> str:
        return f"| {label} | {value(team)} | {value(solo)} |"

    n = len(team)
    rows = [
        row("Moments", lambda a: len(a)),
        row("Graphics put on air", lambda a: sum(x.airs for x in a)),
        row("Judged not worth a graphic", lambda a: sum(x.passed_on for x in a)),
        row(
            "On air with every claim, number, and name checked against the brief",
            lambda a: share(sum(x.clean for x in a), sum(x.airs for x in a)),
        ),
        row(
            "On air with something the brief doesn't support",
            lambda a: sum(x.airs and bool(x.problems) for x in a),
        ),
        row(
            "Held back by the checks (the scripted copy airs instead)",
            lambda a: (
                sum(not x.airs and bool(x.problems) for x in a)
                if a and a[0].system == "team"
                else "no checks"
            ),
        ),
        row(
            "First draft passed both checks",
            lambda a: (
                share(
                    sum(bool(x.first_draft_ok) for x in a),
                    sum(x.first_draft_ok is not None for x in a),
                )
                if a and a[0].system == "team"
                else "no checks"
            ),
        ),
        *(
            row(
                f"Drafts sent back by the {label}",
                lambda a, check=check: (
                    sum(x.sent_back.get(check, 0) for x in a)
                    if a and a[0].system == "team"
                    else "no checks"
                ),
            )
            for check, label in (("checker", "code checker"), ("fact_checker", "fact-checker"))
        ),
        *(row(f"Foundry {e} (1-5)", lambda a, e=e: mean_score(a, e)) for e in EVALUATORS),
        row(
            "Median seconds per moment",
            lambda a: f"{statistics.median([x.seconds for x in a if not x.error] or [0]):.1f}",
        ),
        row(
            "Mean tokens per moment",
            lambda a: f"{statistics.mean([x.tokens for x in a if not x.error] or [0]):,.0f}",
        ),
        row("Errors", lambda a: sum(x.error is not None for x in a)),
    ]
    lines = [
        "# Graphics team vs a single agent",
        "",
        f"Every moment of the featured match ({n}), the same brief to both. Generated by "
        "`python -m app.evals.graphics` on "
        f"{meta['generated_at'][:10]} (matchday `{meta['matchday']}`). Writers: "
        f"{meta['writer_model']}; Foundry's judge: {meta['judge_model']}. "
        "Every answer, check, and score: [graphics.json](graphics.json).",
        "",
        "| | Graphics team | Single agent |",
        "|---|---|---|",
        *rows,
        "",
        "## Moment by moment",
        "",
        "| Min | Moment | Team | Single agent | Single agent's first problem |",
        "|---|---|---|---|---|",
    ]
    for t, s in zip(team, solo, strict=True):
        lines.append(
            f"| {t.minute}' | {t.label} | {_cell(t)} | {_cell(s)} | "
            f"{(s.problems[0] if s.problems else '').replace('|', '/')} |"
        )
    flagged = [a for a in (*team, *solo) if a.passes.get("groundedness") is False]
    lines += [
        "",
        "## What Foundry's judge found ungrounded",
        "",
        "Each graphic that failed groundedness, with the judge's reason in its own words.",
        "",
    ]
    for a in sorted(flagged, key=lambda a: (a.minute, a.system)):
        who = "Graphics team" if a.system == "team" else "Single agent"
        reason = a.reasons.get("groundedness", "").removeprefix("Let's think step by step: ")
        lines += [
            f"- **{a.minute}' {who}** ({a.scores['groundedness']:.0f}/5): "
            f"*{a.headline}. {a.body}*  ",
            f"  {reason}",
        ]
    return "\n".join(lines) + "\n"


def _cell(a: Answer) -> str:
    if a.error:
        return f"error: {a.error[:40]}"
    if a.passed_on:
        return "not worth a graphic"
    if not a.airs:
        return "held back by the checker"
    grounded = a.scores.get("groundedness")
    mark = f" (grounded {grounded:.0f})" if grounded is not None else ""
    return f"{a.headline}{mark}".replace("|", "/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--limit", type=int, default=None, help="only the first N moments")
    asyncio.run(main(parser.parse_args().limit))
