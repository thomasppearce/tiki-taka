"""The whip-around: the Director's cuts, the producer's controls, and the channel API."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.live.channel import GOAL_COUNTDOWN_MS, ChannelDirector
from app.live.service import MatchdayService
from app.models.channel import Channel, Cut

Pin = Callable[..., None]


def watch(director: ChannelDirector, start_min: float, end_min: float) -> list[Cut]:
    """A viewer watching from `start_min` to `end_min`, synced every two seconds."""
    cuts: list[Cut] = []
    for t in range(int(start_min * 60_000), int(end_min * 60_000), 2_000):
        director.sync(t)
        assert director.state
        if not cuts or cuts[-1].cut_id != director.state.on_air.cut_id:
            cuts.append(director.state.on_air)
    return cuts


def test_kickoff_starts_on_the_featured_match(service: MatchdayService) -> None:
    director = ChannelDirector(service)
    director.sync(0)
    assert director.state
    assert director.state.on_air.match_id == "m_l1_1" and director.state.on_air.reason == "kickoff"


def test_every_goal_that_moves_the_table_reaches_the_screen(service: MatchdayService) -> None:
    director = ChannelDirector(service)
    cuts = watch(director, 0, 97)
    for swing in service.swings:
        on_air_then = [
            c for c in cuts if c.clock_ms <= swing.match_clock_ms + GOAL_COUNTDOWN_MS + 2_000
        ]
        assert on_air_then[-1].match_id == swing.match_id, swing.summary
    title = next(c for c in cuts if c.reason == "goal" and c.match_id == "m_l1_2")
    assert title.package.at_stake and "Halvern Town go top" in title.package.at_stake
    goals = {e.event_id for m in service.matches for e in m.result.events if e.type == "goal"}
    assert any(i in goals for claim in title.package.claims for i in claim.evidence_event_ids)


def test_the_feed_moves_but_never_flickers(service: MatchdayService) -> None:
    cuts = watch(ChannelDirector(service), 0, 97)
    stays = [b.clock_ms - a.clock_ms for a, b in zip(cuts, cuts[1:], strict=False)]
    assert 20 <= len(cuts) <= 60
    assert max(stays) <= 8 * 60_000  # quiet spells check in elsewhere
    automatic = [
        b.clock_ms - a.clock_ms
        for a, b in zip(cuts, cuts[1:], strict=False)
        if b.reason == "pressure"
    ]
    assert min(automatic) >= 30_000  # no pressure cut right after another cut


def test_hold_pin_and_take(service: MatchdayService) -> None:
    director = ChannelDirector(service)
    watch(director, 76, 77)
    director.hold(77 * 60_000, True)
    cuts = watch(director, 77, 78.9)  # Halvern score at 78' and the feed stays put
    assert len(cuts) == 1 and cuts[0].match_id != "m_l1_2"
    director.hold(int(78.9 * 60_000), False)
    director.pin(int(79.5 * 60_000), "m_l1_9")
    assert director.state and director.state.on_air.decided_by == "producer"
    assert {c.match_id for c in watch(director, 79.5, 82)} == {"m_l1_9"}
    director.pin(82 * 60_000, None)
    director.take(82 * 60_000, "m_l1_3")
    assert director.state.on_air.match_id == "m_l1_3" and director.state.on_air.reason == "manual"


def test_the_channel_api(client: TestClient, at_minute: Pin) -> None:
    at_minute(60)
    channel = Channel.model_validate(client.get("/api/channel").json())
    assert channel.signals == sorted(channel.signals, key=lambda x: -x.score)
    taken = Channel.model_validate(
        client.post("/api/channel/take", json={"match_id": "m_l1_5"}).json()
    )
    assert taken.on_air.match_id == "m_l1_5" and taken.on_air.decided_by == "producer"
    held = Channel.model_validate(client.post("/api/channel/hold", json={"held": True}).json())
    assert held.held and held.pending is None
    assert client.post("/api/channel/pin", json={"match_id": "m_nope"}).status_code == 404
    client.post("/api/channel/hold", json={"held": False})
