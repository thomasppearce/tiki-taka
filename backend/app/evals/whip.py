"""The whip-around: Watchers and a Director against one agent watching all ten matches, on every
cut of a session, judged on Microsoft Foundry.

    uv run python -m app.evals.whip             # every cut from 55' to full time
    uv run python -m app.evals.whip --limit 5   # a quick look

The channel replays a session from 55' with the code's Director, recording every cut it asks the
Director agent about: why the code wants to cut, its three candidates, and what is on air. Then,
for each cut:
- the team: each candidate's Watcher tells its match's story from that match's brief alone (as
  the Watchers do, ahead of every cut), and the Director, given the three candidates with their
  stories, picks one and writes why and what's at stake. Each is checked, with one retry, as on
  air.
- a single agent, twice: on the Director's fast model and on the Watchers' accurate one, since a
  single agent gets one. Given all ten matches' briefs, the table, and the same three candidates,
  it picks one, writes why and what's at stake, and tells that match's story, with the two
  specialists' instructions word for word and the checker's rules to check its own work.
Then: the channel's checker on what each would put on air; Foundry's evaluators (groundedness,
relevance, coherence) on why, at stake, and the story, against the chosen match's brief; tokens;
and time to the cut. The Director has a countdown (5 s, 3 s for a goal) and can still reword the
cut for 15 s after it; the Watchers write ahead of the cut, so only the Director is on the clock.

Writes docs/evals/whip.json and docs/evals/whip.md.
"""

import argparse
import asyncio
import json
import os
import statistics
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from agent_framework import EvalItem, Message
from agent_framework.foundry import FoundryEvals
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from app.agents.channel_brief import MatchBrief, match_brief
from app.agents.channel_checker import check_decision, check_story
from app.agents.channel_team import (
    DIRECTOR,
    DIRECTOR_GOAL,
    WATCHER,
    ChannelTeam,
    channel_intro,
)
from app.agents.schemas import CutDecision, DraftClaim, StoryUpdate
from app.agents.team import AgentTeam
from app.agents.tracing import start_tracing
from app.evals.graphics import EVALUATORS, OUT
from app.live.channel import CUT_COUNTDOWN_MS, GOAL_COUNTDOWN_MS, LATE_DECISION_MS
from app.live.service import MatchdayService

START_MINUTE = 55
CONCURRENCY = 3
TIMEOUT_S = 120.0

System = Literal["team", "solo_fast", "solo_accurate"]
NAMES: dict[str, str] = {
    "team": "Watchers + Director",
    "solo_fast": "Single agent (fast model)",
    "solo_accurate": "Single agent (accurate model)",
}


@dataclass
class Point:
    """A cut the code asked the Director agent about."""

    t: int
    reason: str
    on_air: str
    candidates: list[str]


class _Recorder:
    """Stands in for the channel's agents: writes down every decision the code asks for."""

    def __init__(self) -> None:
        self.points: list[Point] = []

    def request_story(self, *args: Any) -> None:
        pass

    def request_decision(
        self, channel: Any, key: str, reason: str, on_air: str, briefs: Sequence[MatchBrief]
    ) -> None:
        self.points.append(
            Point(int(key.split(":")[0]), reason, on_air, [b.match_id for b in briefs])
        )


def decision_points(service: MatchdayService) -> list[Point]:
    """Every cut the code asks the Director about, in a session from 55' to the last whistle."""
    recorder = _Recorder()
    director = service.channel
    director.agents = recorder  # type: ignore[assignment]
    # Step through as a viewer's stream would: a gap over 15 s makes the channel start afresh.
    for t in range(START_MINUTE * 60_000, service.over_ms + 1, 5_000):
        director.sync(t)
    director.agents = None
    return recorder.points


class SoloCut(BaseModel):
    """The single agent's answer: the Director's and the Watcher's in one."""

    match_id: str = Field(description="The id of the candidate to cut to.")
    why: str = Field(description="At most 18 words: why we're going there now.")
    at_stake: str | None = Field(
        description="At most 25 words, that match's AT STAKE line in plain words; null if none."
    )
    story: str = Field(description="At most 35 words: that match's story so far, on the pitch.")
    claims: list[DraftClaim] = Field(
        description="Every factual statement in why and story, each citing that match's events."
    )


def solo_instructions(intro: str, goal: bool) -> str:
    return f"""{intro}
You run the channel alone: you watch all ten matches, decide where it cuts, and tell the story of
the match you cut to. Two specialists usually share this work; their instructions follow, word
for word. Do both jobs and give one answer: as the Director, choose one of the candidates and
write why and at_stake; as the Watcher of the match you chose, write its story so far. List as
claims every factual statement in why and in the story, each citing that match's event ids.
Before you answer, check your own work against the rules, as a fact-checker would.

THE DIRECTOR'S INSTRUCTIONS
{DIRECTOR_GOAL if goal else DIRECTOR}

THE WATCHER'S INSTRUCTIONS
{WATCHER}"""


@dataclass
class Answer:
    system: System
    t: int
    minute: int
    reason: str
    candidates: list[str]
    match_id: str | None = None  # the cut it chose
    kept_proposal: bool | None = None
    why: str = ""
    at_stake: str = ""
    story: str = ""
    airs: bool = False  # it puts its own words on air (else the code's package airs)
    problems: list[str] = field(default_factory=list)  # the checker's, on what airs
    held_back: list[str] = field(default_factory=list)  # team: what the checks stopped
    seconds_to_cut: float = 0.0  # the Director's call (team) or the whole call (single agent)
    watcher_seconds: float = 0.0  # team: ahead of the cut, off the clock
    tokens: int = 0
    error: str | None = None
    scores: dict[str, float] = field(default_factory=dict)
    passes: dict[str, bool] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)

    @property
    def countdown_s(self) -> float:
        return (GOAL_COUNTDOWN_MS if self.reason == "goal" else CUT_COUNTDOWN_MS) / 1000


def _answer(system: System, p: Point) -> Answer:
    return Answer(system, p.t, p.t // 60_000 + 1, p.reason, p.candidates)


async def run_team(crew: ChannelTeam, service: MatchdayService, p: Point) -> Answer:
    answer = _answer("team", p)
    start = time.perf_counter()
    told = await asyncio.gather(
        *(crew.story(match_brief(service, c, p.t, None)) for c in p.candidates)
    )
    answer.watcher_seconds = time.perf_counter() - start
    stories = {c: update for c, (update, *_rest) in zip(p.candidates, told, strict=True)}
    answer.tokens = sum(tokens for _, tokens, *_rest in told)
    answer.held_back += [
        f"{c}: the Watcher's story failed the checks" for c, s in stories.items() if not s
    ]
    briefs = [
        match_brief(service, c, p.t, stories[c].story if stories[c] else None) for c in p.candidates
    ]
    start = time.perf_counter()
    decision, tokens, problems, _ = await crew.decide(p.reason, p.on_air, briefs)
    answer.seconds_to_cut = time.perf_counter() - start
    answer.tokens += tokens
    if decision is None:
        answer.held_back.append(f"the Director's decision failed the checks: {problems[0]}")
        return answer
    answer.match_id = decision.match_id
    answer.kept_proposal = decision.match_id == p.candidates[0]
    answer.why, answer.at_stake = decision.why, decision.at_stake or ""
    chosen = stories.get(decision.match_id)
    answer.story = chosen.story if chosen else ""
    answer.airs = chosen is not None  # the cut's words and its Watcher's story, all checked
    return answer


async def run_solo(
    team: AgentTeam, system: System, intro: str, service: MatchdayService, p: Point
) -> Answer:
    answer = _answer(system, p)
    briefs = {m.match_id: match_brief(service, m.match_id, p.t, None) for m in service.matches}
    candidates = [briefs[c] for c in p.candidates]
    prompt = (
        f"ON AIR NOW: {p.on_air}\nWHY THE CODE WANTS TO CUT: {p.reason}\n"
        f"CANDIDATES, THE CODE'S PROPOSAL FIRST: {', '.join(p.candidates)}\n\n"
        + "\n\n".join(b.text(label=f"[{i + 1}] ") for i, b in enumerate(briefs.values()))
    )
    start = time.perf_counter()
    cut, tokens, _ = await team.ask_with_tools(
        "Solo", solo_instructions(intro, p.reason == "goal"), prompt, SoloCut, None
    )
    answer.seconds_to_cut = time.perf_counter() - start
    answer.tokens = tokens
    claims = [c for c in cut.claims if c.evidence_event_ids]
    decision = CutDecision(match_id=cut.match_id, why=cut.why, at_stake=cut.at_stake, claims=claims)
    answer.problems = check_decision(decision, candidates)
    if cut.match_id in briefs:
        update = StoryUpdate(story=cut.story, claims=claims)
        answer.problems += check_story(update, briefs[cut.match_id])
    answer.match_id = cut.match_id
    answer.kept_proposal = cut.match_id == p.candidates[0]
    answer.why, answer.at_stake, answer.story = cut.why, cut.at_stake or "", cut.story
    answer.airs = cut.match_id in p.candidates  # nobody checks it: what it writes goes on air
    return answer


def _text(a: Answer) -> str:
    return f"WHY: {a.why}\nAT STAKE: {a.at_stake or 'nothing'}\nSTORY: {a.story}"


async def judge(
    team: AgentTeam, judge_model: str, service: MatchdayService, answers: list[Answer], name: str
) -> str:
    """Foundry's evaluators on what each would put on air, against the chosen match's brief."""
    airing = [a for a in answers if a.airs and a.match_id]
    if not airing:
        return ""
    contexts = {id(a): match_brief(service, a.match_id or "", a.t, None).text() for a in airing}
    items = [
        EvalItem(
            conversation=[Message("user", [contexts[id(a)]]), Message("assistant", [_text(a)])],
            context=contexts[id(a)],
        )
        for a in airing
    ]
    evals = FoundryEvals(
        client=team.client, model=judge_model, evaluators=EVALUATORS, timeout=1200.0
    )
    results = await evals.evaluate(items, eval_name=name)
    by_text = {(contexts[id(a)], _text(a)): a for a in airing}
    page = await team.client.client.evals.runs.output_items.list(
        run_id=results.run_id, eval_id=results.eval_id
    )
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
    points = decision_points(service)[:limit]
    fast = AgentTeam.from_env(knowledge=False)
    accurate = AgentTeam.from_env("FOUNDRY_WATCHER_MODEL", knowledge=False)
    await start_tracing(fast.client)
    intro = channel_intro(service.matchday_number, service.last_matchday)
    crew = ChannelTeam(fast, accurate, intro=intro)
    gate = asyncio.Semaphore(CONCURRENCY)

    async def gated(system: System, p: Point) -> Answer:
        async with gate:
            try:
                if system == "team":
                    run = run_team(crew, service, p)
                else:
                    team = fast if system == "solo_fast" else accurate
                    run = run_solo(team, system, intro, service, p)
                answer = await asyncio.wait_for(run, TIMEOUT_S)
            except Exception as error:
                answer = _answer(system, p)
                answer.error = "timed out" if isinstance(error, TimeoutError) else repr(error)
        flags = f", {len(answer.problems)} problems" if answer.problems else ""
        print(
            f"{system:>13} {answer.minute:>3}' {p.reason:<9} -> {answer.match_id} "
            f"{answer.seconds_to_cut:.1f} s{flags}{' ' + answer.error if answer.error else ''}",
            flush=True,
        )
        return answer

    systems: tuple[System, ...] = ("team", "solo_fast", "solo_accurate")
    print(f"{len(points)} cuts, {len(systems)} systems, {CONCURRENCY} at a time")
    answers = await asyncio.gather(*(gated(s, p) for p in points for s in systems))
    judge_model = os.environ.get("FOUNDRY_WATCHER_MODEL") or fast.model
    print("judging on Foundry")
    by_system = {s: [a for a in answers if a.system == s] for s in systems}
    reports = {
        s: await judge(
            fast, judge_model, service, by_system[s], f"Tiki-Taka whip-around: {NAMES[s]}"
        )
        for s in systems
    }
    meta = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "matchday": service.fingerprint,
        "fast_model": os.environ.get("FOUNDRY_MODEL_LABEL", fast.model),
        "accurate_model": accurate.model,
        "judge_model": judge_model,
        "evaluators": EVALUATORS,
        "reports": reports,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {**meta, "answers": [asdict(a) for a in answers]}
    (OUT / "whip.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    summary = render(meta, by_system, len(points))
    (OUT / "whip.md").write_text(summary)
    print(summary)


def render(meta: dict[str, Any], by_system: dict[System, list[Answer]], cuts: int) -> str:
    systems = list(by_system)

    def row(label: str, value: Any) -> str:
        return f"| {label} | " + " | ".join(str(value(by_system[s])) for s in systems) + " |"

    def share(part: int, whole: int) -> str:
        return f"{part}/{whole} ({part / whole:.0%})" if whole else "0/0"

    def mean_score(answers: list[Answer], name: str) -> str:
        scores = [a.scores[name] for a in answers if name in a.scores]
        passed = sum(a.passes.get(name, False) for a in answers if name in a.passes)
        return f"{statistics.mean(scores):.2f} ({passed}/{len(scores)} pass)" if scores else "n/a"

    def ok(a: list[Answer]) -> list[Answer]:
        return [x for x in a if not x.error]

    lines = [
        "# The whip-around: Watchers and a Director vs a single agent",
        "",
        f"Every cut the code asked the Director about in a session from {START_MINUTE}' to the "
        f"last whistle ({cuts}). Generated by `python -m app.evals.whip` on "
        f"{meta['generated_at'][:10]} (matchday `{meta['matchday']}`). Fast model: "
        f"{meta['fast_model']}; accurate model: {meta['accurate_model']}; Foundry's judge: "
        f"{meta['judge_model']}. Every answer: [whip.json](whip.json).",
        "",
        "| | " + " | ".join(NAMES[s] for s in systems) + " |",
        "|---|" + "---|" * len(systems),
        row("Cuts", lambda a: len(a)),
        row(
            "On air in its own words, all checked",
            lambda a: share(sum(x.airs and not x.problems for x in a), len(a)),
        ),
        row(
            "On air with something the checker rejects",
            lambda a: sum(x.airs and bool(x.problems) for x in a),
        ),
        row(
            "Held back by the checks (the code's words air)",
            lambda a: (
                sum(bool(x.held_back) and not x.airs for x in a)
                if a and a[0].system == "team"
                else "no checks"
            ),
        ),
        *(row(f"Foundry {e} (1-5)", lambda a, e=e: mean_score(a, e)) for e in EVALUATORS),
        row(
            "Decided before the countdown ends",
            lambda a: share(sum(x.seconds_to_cut <= x.countdown_s for x in ok(a)), len(ok(a))),
        ),
        row(
            "In time to word the cut (countdown + 15 s)",
            lambda a: share(
                sum(x.seconds_to_cut <= x.countdown_s + LATE_DECISION_MS / 1000 for x in ok(a)),
                len(ok(a)),
            ),
        ),
        row(
            "Median seconds to the cut",
            lambda a: f"{statistics.median([x.seconds_to_cut for x in ok(a)] or [0]):.1f}",
        ),
        row(
            "Mean tokens per cut",
            lambda a: f"{statistics.mean([x.tokens for x in ok(a)] or [0]):,.0f}",
        ),
        row(
            "Kept the code's proposal",
            lambda a: share(sum(bool(x.kept_proposal) for x in a), len(a)),
        ),
        row("Errors", lambda a: sum(x.error is not None for x in a)),
    ]
    flagged = [x for s in systems for x in by_system[s] if x.passes.get("groundedness") is False]
    lines += ["", "## What Foundry's judge found ungrounded", ""]
    for x in sorted(flagged, key=lambda x: (x.t, x.system)):
        reason = x.reasons.get("groundedness", "").removeprefix("Let's think step by step: ")
        lines += [
            f"- **{x.minute}' {NAMES[x.system]}** ({x.scores['groundedness']:.0f}/5): "
            f"*{x.why} {x.story}*  ",
            f"  {reason}",
        ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--limit", type=int, default=None, help="only the first N cuts")
    asyncio.run(main(parser.parse_args().limit))
