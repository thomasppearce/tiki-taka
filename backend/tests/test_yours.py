"""A fan's own matchday beside the recap: written by code, a different day for each club and
each XI, and nothing for the main channel."""

from fastapi.testclient import TestClient

from app.generator.season import TEAM_OF_THE_SEASON
from app.live.service import MatchdayService
from app.live.yours import your_day


def test_each_club_gets_its_own_day(service: MatchdayService) -> None:
    headlines = {
        club: your_day(service, f"club:{club}", True, 0).headline
        for club in ("t_hvt", "t_ngr", "t_wma", "t_crb", "t_pha", "t_tdr")
    }
    assert headlines == {
        "t_hvt": "Halvern Town are champions",
        "t_ngr": "Northgate Rovers miss out on the title",
        "t_wma": "Westmere Athletic stay up",  # an hour in the drop zone, out at 93'
        "t_crb": "Corrin Bay are relegated",
        "t_pha": "Porthallow Athletic make the top four",
        "t_tdr": "Tidewick Rovers miss out on the top four",
    }


def test_a_club_day_cites_its_result_and_the_goals_that_moved_it(
    service: MatchdayService,
) -> None:
    day = your_day(service, "club:t_wma", True, 0)
    *swings, result, position = day.lines
    assert result.fact_id == "ft:m_l1_1" and "Desai 73', 93'" in result.text
    assert [s.minute for s in swings] == [32, 93]  # into the drop zone, then out of it
    assert all(":evt_" in s.fact_id for s in swings)
    assert (
        position.text == "Westmere Athletic finish 17th, where they started the day, on 40 points."
    )


def test_a_fantasy_day_leads_with_the_points(service: MatchdayService) -> None:
    day = your_day(service, "xi:" + ",".join(TEAM_OF_THE_SEASON), True, 0)
    assert day.kind == "fantasy" and day.points is not None
    assert day.headline == f"Your XI scored {day.points} points: Blackwood led with 18"
    assert day.lines[0].text == "Kofi Blackwood (ELR): 18 pts, 4 goals."


def test_the_main_channel_has_no_day_of_its_own_and_nobody_gets_one_early(
    service: MatchdayService, client: TestClient
) -> None:
    assert your_day(service, None, True, 0).headline is None
    assert your_day(service, "club:t_wma", False, 0).status == "pending"
    assert (
        client.get("/api/recap/yours", params={"lens": "club:nope", "ended": True}).status_code
        == 400
    )
