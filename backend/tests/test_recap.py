"""How the final day unfolded (app/live/recap.py, app/agents/recap.py): facts by code, the story
by the recap writer, checked, with the code's recap when no draft passes."""

import asyncio
from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.recap import check_recap
from app.agents.schemas import RecapBeatDraft, RecapDraft
from app.live.recap import RecapDesk, _outcomes, code_recap, day_facts
from app.live.service import MatchdayService
from app.models.recap import RecapFact


def _moments(facts: list[RecapFact]) -> list[RecapFact]:
    return [f for f in facts if f.minute is not None]


def test_the_facts_say_how_every_race_ended(service: MatchdayService) -> None:
    facts = {f.fact_id: f for f in day_facts(service)}
    assert {
        "table:top",
        "table:top_four",
        "table:bottom",
        "table:golden_boot",
        "table:deciders",
    } <= set(facts)
    assert sum(i.startswith("ft:") for i in facts) == len(service.matches)
    assert "Westmere Athletic stay up" in facts["table:bottom"].text
    assert "Halvern Town are champions" in facts["table:top"].text


def test_each_moment_is_one_goal_in_its_own_match(service: MatchdayService) -> None:
    moments = _moments(day_facts(service))
    assert len({m.fact_id for m in moments}) == len(moments)
    for moment in moments:
        match_id, event_id = moment.fact_id.split(":")
        goal = next(e for e in service.by_id[match_id].result.events if e.event_id == event_id)
        assert goal.type == "goal" and moment.match_id == match_id
        assert " scores for " in moment.text
    assert [m.minute for m in moments] == sorted(m.minute or 0 for m in moments)


def test_the_code_recap_tells_the_day_from_the_facts(service: MatchdayService) -> None:
    facts = day_facts(service)
    headline, standfirst, beats = code_recap(facts)
    assert headline == "Halvern Town are champions"
    assert [b.fact_ids[0] for b in beats] == [m.fact_id for m in _moments(facts)]
    assert (
        check_recap(
            RecapDraft(
                headline=headline,
                standfirst=standfirst,
                beats=[
                    RecapBeatDraft(minute=b.minute, text=b.text, fact_ids=b.fact_ids) for b in beats
                ],
            ),
            facts,
            _names(service),
        )
        == []
    )


def _names(service: MatchdayService) -> frozenset[str]:
    return RecapDesk(service).names()


def test_the_checker_holds_each_beat_to_the_facts_it_cites(service: MatchdayService) -> None:
    facts = day_facts(service)
    decider = _moments(facts)[-1]  # Desai's 93rd-minute winner
    good = RecapBeatDraft(
        minute=93, text="Desai's winner saves Westmere.", fact_ids=[decider.fact_id]
    )
    bad = [
        RecapBeatDraft(minute=93, text="A winner.", fact_ids=["m_l1_1:evt_999999"]),
        RecapBeatDraft(minute=90, text="Desai's winner.", fact_ids=[decider.fact_id]),
        RecapBeatDraft(minute=93, text="Desai scores his 30th.", fact_ids=[decider.fact_id]),
        RecapBeatDraft(minute=93, text="Ambrose looks on.", fact_ids=[decider.fact_id]),
        RecapBeatDraft(
            minute=25, text="Marlow had scored early.", fact_ids=[_moments(facts)[0].fact_id]
        ),
    ]
    draft = RecapDraft(
        headline="Halvern Town win it", standfirst="A day of swings.", beats=[good, *bad]
    )
    problems = check_recap(draft, facts, _names(service))
    assert any("which aren't facts" in p for p in problems)
    assert any("is set at 90'" in p for p in problems)
    assert any("says 30" in p for p in problems)
    assert any("names Ambrose" in p for p in problems)
    assert any("out of time order" in p for p in problems)


def test_with_the_agents_off_the_code_writes_the_recap(
    service: MatchdayService, at_minute: Callable[..., None]
) -> None:
    desk = RecapDesk(service)
    assert desk.snapshot(60 * 60_000).status == "pending"
    recap = desk.snapshot(service.over_ms)
    assert recap.status == "ready" and recap.written_by == "code"
    assert recap.season_over and recap.matchday == 38
    assert recap.top and recap.top.name == "Halvern Town"
    assert [c.name for c in recap.bottom_three] == [
        "Corrin Bay",
        "Dunhallow United",
        "Lanterne Port FC",
    ]
    assert recap.golden_boot and recap.golden_boot.name == "Marco Desai"


class FakeWriter:
    version, model = "test", "fake"

    def __init__(self, fail: bool = False) -> None:
        self.fail, self.calls = fail, 0

    async def write(
        self, facts: list[RecapFact], names: frozenset[str], last_day: bool
    ) -> tuple[RecapDraft | None, int, list[str]]:
        self.calls += 1
        if self.fail:
            return None, 900, ["The fact-checker sent draft 3 back: wrong club"]
        decider = _moments(facts)[-1]
        beat = RecapBeatDraft(
            minute=93, text="Desai's winner saves Westmere.", fact_ids=[decider.fact_id]
        )
        return (
            RecapDraft(headline="Halvern Town win it", standfirst="A day of swings.", beats=[beat]),
            900,
            [],
        )


def _write(service: MatchdayService, writer: FakeWriter, cache: Path) -> tuple[str, object]:
    async def scenario() -> tuple[str, object]:
        desk = RecapDesk(service, writer, cache_dir=cache)  # type: ignore[arg-type]
        desk.start()
        first = desk.snapshot(service.over_ms).status
        for _ in range(50):
            await asyncio.sleep(0.01)
            if desk.snapshot(service.over_ms).status == "ready":
                break
        return first, desk.snapshot(service.over_ms)

    return asyncio.run(scenario())


def test_the_writer_tells_the_story_once_and_it_is_kept(
    service: MatchdayService, tmp_path: Path
) -> None:
    writer = FakeWriter()
    first, recap = _write(service, writer, tmp_path)
    assert first == "writing"
    assert recap.written_by == "agents" and recap.beats[0].match_id == "m_l1_1"  # type: ignore[attr-defined]
    _, again = _write(service, writer, tmp_path)  # a new desk, the same cache on disk
    assert writer.calls == 1 and again.headline == "Halvern Town win it"  # type: ignore[attr-defined]


def test_when_no_draft_passes_the_code_writes_it(service: MatchdayService, tmp_path: Path) -> None:
    _, recap = _write(service, FakeWriter(fail=True), tmp_path)
    assert recap.written_by == "code"  # type: ignore[attr-defined]
    assert recap.checks == ["The fact-checker sent draft 3 back: wrong club"]  # type: ignore[attr-defined]


def test_the_recap_api(
    client: TestClient, at_minute: Callable[..., None], service: MatchdayService
) -> None:
    at_minute(63)
    assert client.get("/api/recap").json()["status"] == "pending"
    at_minute(service.over_ms / 60_000 + 0.5)
    recap = client.get("/api/recap").json()
    assert recap["status"] == "ready" and recap["headline"] == "Halvern Town are champions"


def test_mid_season_the_recap_says_where_the_round_left_the_table(service: MatchdayService) -> None:
    final = service.table_at(service.over_ms)
    round_30 = final.model_copy(
        update={"rows": [r.model_copy(update={"played": 30}) for r in final.rows]}
    )
    facts = {f.fact_id: f.text for f in _outcomes(service, round_30)}
    assert facts["table:top"].startswith("Halvern Town top the table after matchday 30")
    assert facts["table:bottom"].startswith("The bottom three after matchday 30")
    assert facts["table:golden_boot"].startswith("Leading the Golden Boot race")
    assert "top spot at 79'" in facts["table:deciders"]
    assert not any(word in " ".join(facts.values()) for word in ("champions", "Relegated"))


def test_a_match_recap_waits_for_its_whistle_then_the_code_writes_it(
    client: TestClient, at_minute: Callable[..., None], service: MatchdayService
) -> None:
    at_minute(63)
    assert client.get("/api/matches/m_l1_1/recap").json()["status"] == "pending"
    early = client.get("/api/matches/m_l1_1/recap", params={"ended": True}).json()
    assert early["status"] == "ready"  # the /recap page: the finished match on demand
    assert early["headline"] == "Westmere Athletic beat Northgate Rovers 2-1"
    assert early["written_by"] == "code"
    assert [c["evidence_event_ids"] for c in early["claims"]] == [
        ["evt_000782"],
        ["evt_002107"],
        ["evt_002634"],
    ]
    assert client.get("/api/recap", params={"ended": True}).json()["status"] == "ready"
    every = client.get("/api/recaps", params={"ended": True}).json()
    assert len(every) == len(service.matches) and {r["status"] for r in every} == {"ready"}


def test_a_match_recap_gives_the_final_score_and_stays_on_the_pitch(
    service: MatchdayService,
) -> None:
    from app.agents.channel_brief import match_brief
    from app.agents.channel_checker import check_match_recap
    from app.agents.schemas import DraftClaim, MatchRecapDraft

    m = service.by_id["m_l1_1"]
    brief = match_brief(service, "m_l1_1", m.result.full_time_ms, None, full=True)
    winner = DraftClaim(text="Desai scored the winner", evidence_event_ids=["evt_002634"])
    good = MatchRecapDraft(
        headline="Desai wins it late", story="Westmere won 2-1 at Northgate.", claims=[winner]
    )
    assert check_match_recap(good, brief) == []
    shots = good.model_copy(update={"story": "Westmere won 2-1, though out-shot 11-7."})
    assert check_match_recap(shots, brief) == []  # a stat compared, not a scoreline
    bad = MatchRecapDraft(
        headline="Desai keeps Westmere up",
        story="Westmere led 2-0 and stayed out of the relegation zone.",
        claims=[winner],
    )
    problems = " ".join(check_match_recap(bad, brief))
    assert "doesn't give the final score: 1-2" in problems
    assert "says 2-0, which this match never was" in problems
    assert "talks about the table" in problems


def test_the_producer_can_skip_to_the_final_whistle_and_back(
    client: TestClient, service: MatchdayService
) -> None:
    skipped = client.post("/api/clock", json={}).json()["clock_ms"]
    assert skipped >= service.over_ms
    assert client.get("/api/recap").json()["status"] in ("writing", "ready")
    back = client.post("/api/clock", json={"minute": 55}).json()["clock_ms"]
    assert 55 * 60_000 <= back < 55 * 60_000 + 5_000  # where a cold start begins
    assert client.get("/api/recap").json()["status"] == "pending"
    assert client.post("/api/clock", json={"minute": 500}).status_code == 422
