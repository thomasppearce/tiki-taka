"""The players' stories: a season that adds up, a Golden Boot race decided at the death, and the
personal stories the final day settles, all written by code for the agents to cite."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.agents.channel_brief import match_brief
from app.agents.channel_checker import check_story
from app.agents.schemas import StoryUpdate
from app.generator.player_season import GOLDEN_BOOT, OTHERS_MAX
from app.generator.season import table_before_final_day
from app.live.channel import ChannelDirector
from app.live.service import MatchdayService

Pin = Callable[..., None]


def test_the_season_adds_up_and_sets_up_the_race(service: MatchdayService) -> None:
    table = {r.club_id: r for r in table_before_final_day()}
    for club in service.clubs.values():
        goals = sum(service.player_seasons[p.player_id].goals for p in club.squad)
        assert goals == table[club.club_id].goals_for, club.name
    assert {p: service.player_seasons[p].goals for p in GOLDEN_BOOT} == GOLDEN_BOOT
    others = [r.goals for p, r in service.player_seasons.items() if p not in GOLDEN_BOOT]
    assert max(others) <= OTHERS_MAX  # nobody else can catch them, even with a hat-trick


def test_the_golden_boot_is_won_at_the_death(service: MatchdayService) -> None:
    swings = [(service.surname(s.player_id), s.summary) for s in service.boot_swings]
    assert [who for who, _ in swings] == ["Marlow", "Desai", "Ambrose", "Desai"]
    assert "three-way tie" in swings[0][1] and "draws level" in swings[2][1]
    final = service._table(99 * 60).golden_boot
    assert [(r.position, service.surname(r.player_id), r.goals) for r in final.rows[:3]] == [
        (1, "Desai", 24),
        (2, "Ambrose", 23),
        (3, "Marlow", 22),
    ]
    assert service.boot_swings[-1].event_id == final.swings[-1].event_id
    winner = [e for e in service.by_id["m_l1_1"].result.events if e.type == "goal"][-1]
    assert service.boot_swings[-1].event_id == winner.event_id  # the goal that kept Westmere up


def test_the_days_personal_stories(service: MatchdayService) -> None:
    def stories(match_id: str, minute: float) -> str:
        return " | ".join(service.stories(match_id, int(minute * 60_000)))

    assert "Radcliffe is one short of 100 league goals" in stories("m_l1_3", 20)
    assert "goal is his 100th league goal for Corrin Bay" in stories("m_l1_3", 40)
    assert "Marlow faces Westmere Athletic" in stories("m_l1_1", 10)
    assert "Marlow scores against Westmere Athletic" in stories("m_l1_1", 40)
    assert "Jervaise's last game" in stories("m_l1_2", 60)
    assert "the Coast derby" in stories("m_l1_8", 5)
    assert "Desai leads the Golden Boot race on 24" in stories("m_l1_1", 96)
    # A goal that moved the race leads its cut's package.
    winner = [e for e in service.by_id["m_l1_1"].result.events if e.type == "goal"][-1]
    package = ChannelDirector(service)._package("m_l1_1", "goal", winner.match_clock_ms, winner)
    assert package.storyline == "Desai goes top of the Golden Boot race on 24."


def test_agents_get_the_stories_and_may_use_them(service: MatchdayService) -> None:
    brief = match_brief(service, "m_l1_3", 40 * 60_000, None)
    assert "PLAYER STORIES:" in brief.text(watcher=True) and "100th" in brief.text()
    goal = next(e for e in service.by_id["m_l1_3"].result.events if e.type == "goal")
    story = StoryUpdate(
        story=f"Corrin Bay lead 1-0, and Radcliffe's {goal.minute + 1}' goal is his 100th league "
        "goal for them.",
        claims=[],
    )
    assert check_story(story, brief) == []  # a goal count, not table talk
    decider = match_brief(service, "m_l1_1", 73 * 60_000, None)
    boot = StoryUpdate(
        story="It's 1-1, and Desai goes top of the Golden Boot race on 23.", claims=[]
    )
    assert check_story(boot, decider) == []


def test_the_table_carries_the_golden_boot(client: TestClient, at_minute: Pin) -> None:
    at_minute(75)
    boot = client.get("/api/table").json()["golden_boot"]
    assert boot["rows"][0]["name"] == "Marco Desai" and boot["rows"][0]["goals"] == 23
    assert len(boot["swings"]) == 2  # the three-way tie, then Desai top
