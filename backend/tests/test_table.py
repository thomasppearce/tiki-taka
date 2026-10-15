"""As it stands: the table, the day's swings, and the stakes the Director weighs."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.live.service import MatchdayService
from app.models.table import LeagueTable

Pin = Callable[..., None]


def test_the_day_swings_in_story_order(service: MatchdayService) -> None:
    summaries = [s.summary for s in service.swings]
    title = summaries.index("Halvern Town go top on goal difference; Northgate Rovers drop to 2nd.")
    down, out = "drop into the relegation zone", "climb out of the relegation zone"
    drop = summaries.index(f"Corrin Bay {out}; Westmere Athletic {down}.")
    saved = summaries.index(f"Westmere Athletic {out}; Corrin Bay {down}.")
    assert drop < title < saved
    goals = {e.event_id: e for m in service.matches for e in m.result.events if e.type == "goal"}
    assert all(s.event_id in goals for s in service.swings)  # every swing cites its goal


def test_the_final_table(service: MatchdayService, at_minute: Pin) -> None:
    at_minute(97)  # every match has ended
    table = service.table()
    zones = {r.club.short: r.zone for r in table.rows}
    assert zones["HVT"] == "champions" and zones["NGR"] == "continental"
    assert zones["WMA"] is None and zones["CRB"] == "relegation"
    assert all(r.played == 38 for r in table.rows)
    assert [r.position for r in table.rows] == list(range(1, 21))


def test_stakes_say_what_a_goal_would_change(service: MatchdayService, at_minute: Pin) -> None:
    at_minute(75)  # NGR 1-1 WMA, BRK 0-0 HVT, CRB 1-0 MBT
    table = service.table()
    stakes = {(s.match_id, s.scorer_club_id): s for s in table.stakes}
    title = stakes[("m_l1_2", "t_hvt")]
    assert title.weight == 1.0 and "Halvern Town go top" in title.summary
    survival = stakes[("m_l1_1", "t_wma")]
    assert survival.weight == 1.0 and "Westmere Athletic climb out" in survival.summary
    assert ("m_l1_3", "t_mbt") in stakes  # a Millbrook equaliser would save Westmere too
    assert ("m_l1_1", "t_ngr") not in stakes  # Northgate are top either way
    assert table.stakes == sorted(table.stakes, key=lambda s: -s.weight)


def test_the_table_endpoint(client: TestClient, at_minute: Pin) -> None:
    at_minute(82)
    table = LeagueTable.model_validate(client.get("/api/table").json())
    assert len(table.rows) == 20
    assert table.rows[0].club.short == "HVT"  # Halvern scored at 80'
    assert all(s.match_clock_ms <= table.clock_ms for s in table.swings)


def test_a_table_for_a_moment_has_no_stakes_in_matches_over_by_then(
    service: MatchdayService,
) -> None:
    """The table as of a moment (an agent's brief, an eval) doesn't depend on the live clock."""
    m = service.by_id["m_l1_1"]
    later = service.table_at(m.result.full_time_ms + 1_000)
    assert not [s for s in later.stakes if s.match_id == "m_l1_1"]
    earlier = service.table_at(m.result.full_time_ms - 60_000)
    assert [s for s in earlier.stakes if s.match_id == "m_l1_1"]
