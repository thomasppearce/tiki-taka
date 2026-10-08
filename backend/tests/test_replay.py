"""Replays: the move behind a goal or a chance, never anything that hasn't happened."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.live.channel import ChannelDirector
from app.live.replay import MAX_BUILD_UP_MS
from app.live.service import MatchdayService
from app.models.replay import Replay

Pin = Callable[..., None]


def halvern_goal(service: MatchdayService) -> str:
    return next(e.event_id for e in service.by_id["m_l1_2"].result.events if e.type == "goal")


def test_a_goal_replay_shows_the_move(service: MatchdayService, at_minute: Pin) -> None:
    at_minute(85)
    replay = service.replay("m_l1_2", halvern_goal(service))
    assert replay and replay.kind == "goal" and replay.label.endswith("scores for Halvern Town")
    assert replay.as_it_stands and "Halvern Town go top" in replay.as_it_stands
    shot = next(e for e in replay.events if e.type == "shot")
    assert replay.from_ms < shot.match_clock_ms < replay.to_ms
    assert replay.slow_from_ms <= shot.match_clock_ms <= replay.slow_to_ms
    assert replay.to_ms - replay.from_ms <= MAX_BUILD_UP_MS + 3_000
    assert [e.type for e in replay.events].count("goal") == 1
    clocks = [f.match_clock_ms for f in replay.frames]
    assert clocks == sorted(clocks) and clocks[0] == replay.from_ms


def test_no_replay_of_what_hasnt_happened(
    client: TestClient, service: MatchdayService, at_minute: Pin
) -> None:
    at_minute(70)  # Halvern score at 78'
    goal = halvern_goal(service)
    assert client.get(f"/api/matches/m_l1_2/replays/{goal}").status_code == 404
    at_minute(80)
    replay = Replay.model_validate(client.get(f"/api/matches/m_l1_2/replays/{goal}").json())
    assert replay.event_id == goal
    assert client.get("/api/matches/m_l1_2/replays/evt_nope").status_code == 404


def test_goal_cuts_open_with_the_goal(service: MatchdayService) -> None:
    director = ChannelDirector(service)
    goals = {e.event_id for m in service.matches for e in m.result.events if e.type == "goal"}
    shots = {e.event_id for m in service.matches for e in m.result.events if e.type == "shot"}
    seen = []
    for t in range(0, 97 * 60_000, 2_000):
        director.sync(t)
        assert director.state
        cut = director.state.on_air
        if not seen or seen[-1].cut_id != cut.cut_id:
            seen.append(cut)
    for cut in seen:
        if cut.reason == "goal":
            assert cut.replay_event_id in goals
        elif cut.replay_event_id:  # pressure cuts and check-ins replay a recent big chance
            assert cut.replay_event_id in shots and cut.reason in ("pressure", "check_in")
    assert any(c.reason != "goal" and c.replay_event_id for c in seen)
