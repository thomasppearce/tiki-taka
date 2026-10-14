"""The failure drill (app/agents/drill.py): an agent fails on purpose, and the system recovers."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agents import drill as drill_module
from app.agents import team as team_module
from app.agents.drill import DRILL, AgentUnavailable
from app.live.service import MatchdayService
from tests.test_agents import FakeTeam, ScriptedTeam, goal_brief, run_first_moment


@pytest.fixture(autouse=True)
def no_drill(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(team_module, "RETRY_AFTER_S", 0)
    DRILL.end()
    yield
    DRILL.end()


def test_a_blip_is_retried_and_the_run_carries_on(service: MatchdayService) -> None:
    brief = goal_brief(service)
    team = ScriptedTeam(brief)
    team.drafts = [team.drafts[1]]  # one draft: the retry must not cost a draft
    DRILL.start("explainer", "blip")
    steps: list[tuple[str, str, str]] = []
    outcome = asyncio.run(team.run(brief, lambda *step: steps.append(step)))
    assert outcome.status == "proposed"
    explainer = [(action, detail) for agent, action, detail in steps if agent == "explainer"]
    assert explainer[0] == (
        "agent_failure",
        "Call failed (Explainer unavailable (failure drill)); retrying in 0 s",
    )
    assert explainer[1] == ("retry", "Retry succeeded")
    assert DRILL.agent is None  # a blip is one failure


def test_an_agent_that_is_down_stops_the_run_after_its_retry(service: MatchdayService) -> None:
    brief = goal_brief(service)
    team = ScriptedTeam(brief)
    DRILL.start("fact_checker", "down")
    steps: list[tuple[str, str, str]] = []
    with pytest.raises(AgentUnavailable, match="Fact-checker unavailable"):
        asyncio.run(team.run(brief, lambda *step: steps.append(step)))
    assert [d for a, _, d in steps if a == "fact_checker"][-1] == (
        "Call failed again (Fact-checker unavailable (failure drill))"
    )
    assert DRILL.agent == "fact_checker"  # down stays down until it ends


def test_in_a_drill_the_team_runs_live_and_is_not_cached(
    service: MatchdayService, tmp_path: Path
) -> None:
    team = FakeTeam()
    run_first_moment(service, team, tmp_path)  # cached now
    DRILL.start("explainer", "down")
    run_first_moment(service, team, tmp_path)
    assert team.calls == 2  # not replayed from the cache: the drill's failure is real
    DRILL.end()
    run_first_moment(service, team, tmp_path)
    assert team.calls == 2  # and the ordinary run is still the one cached


def test_a_drill_ends_by_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(drill_module.time, "monotonic", lambda: now[0])
    DRILL.start("watcher", "down")
    assert DRILL.state().seconds_left == drill_module.DOWN_FOR_S
    now[0] += drill_module.DOWN_FOR_S + 1
    assert DRILL.state().agent is None


def test_the_drill_api(client: TestClient) -> None:
    started = client.post("/api/drill", json={"agent": "director", "mode": "down"}).json()
    assert started["agent"] == "director" and started["mode"] == "down"
    assert client.get("/api/drill").json()["agent"] == "director"
    assert client.post("/api/drill/end").json()["agent"] is None
    assert client.post("/api/drill", json={"agent": "checker", "mode": "down"}).status_code == 422
