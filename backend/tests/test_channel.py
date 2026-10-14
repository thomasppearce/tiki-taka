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
    """On air when it goes in (the feed was already there) or within seconds (a goal cut). Which
    of the two can hinge on a near-tie in the signals, so either is right."""
    cuts = watch(ChannelDirector(service), 0, 97)
    goals = {e.event_id for m in service.matches for e in m.result.events if e.type == "goal"}
    for swing in service.swings:
        soon = swing.match_clock_ms + GOAL_COUNTDOWN_MS + 2_000
        on_air = [c for c in cuts if c.clock_ms <= soon][-1]
        assert on_air.match_id == swing.match_id, swing.summary
        if on_air.reason == "goal":
            assert on_air.package.at_stake == f"As it stands: {swing.summary}"
            cited = {i for claim in on_air.package.claims for i in claim.evidence_event_ids}
            assert swing.event_id in cited and cited <= goals


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
    director.take(77 * 60_000, "m_l1_5")  # elsewhere when Halvern score at 78'...
    director.hold(77 * 60_000, True)
    cuts = watch(director, 77, 78.9)  # ...and, held, the feed stays put
    assert {c.match_id for c in cuts} == {"m_l1_5"}
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


def test_the_channel_knows_a_dead_ball_and_goes_to_a_penalty(service: MatchdayService) -> None:
    """A restart being set up is dead time (the feed may cut away); a penalty is the opposite,
    and the channel goes there."""
    director = ChannelDirector(service)
    events = service.by_id["m_l1_5"].result.events
    throw = next(e for e in events if e.type == "throw_in" and e.match_clock_ms > 30 * 60_000)
    played = next(e for e in events if e.type == "pass" and e.match_clock_ms > throw.match_clock_ms)
    assert director._dead_since("m_l1_5", throw.match_clock_ms + 1_000) == throw.match_clock_ms
    assert director._dead_since("m_l1_5", played.match_clock_ms + 500) is None

    award = next(
        (e, m.match_id) for m in service.matches for e in m.result.events if e.type == "penalty"
    )
    penalty, match_id = award
    quiet = next(
        m.match_id
        for m in service.matches
        if m.match_id != match_id
        and not any(
            e.type == "goal" and abs(e.match_clock_ms - penalty.match_clock_ms) < 3 * 60_000
            for e in m.result.events
        )
    )
    start = penalty.match_clock_ms // 1_000 * 1_000 - 30_000
    director.sync(start)
    director.take(start, quiet)
    for t in range(start, penalty.match_clock_ms + 2_000, 1_000):
        director.sync(t)
    assert director.state and director.state.pending
    assert (director.state.pending.match_id, director.state.pending.reason) == (match_id, "penalty")
    assert director.state.pending.package.why.startswith("Penalty to ")


def test_viewers_joining_in_the_same_minute_get_the_same_channel(service: MatchdayService) -> None:
    """The channel starts from the top of the minute, so a cold start's first visitors (and the
    agents' cached answers for them) all see the same cuts."""
    early, late = ChannelDirector(service), ChannelDirector(service)
    cuts_early = watch(early, 55 + 10 / 60, 62)
    cuts_late = watch(late, 55 + 50 / 60, 62)
    assert [(c.cut_id, c.match_id) for c in cuts_early] == [
        (c.cut_id, c.match_id) for c in cuts_late
    ]


def test_the_channel_knows_which_matchday_it_covers(client: TestClient) -> None:
    from app.agents.channel_team import channel_intro

    day = client.get("/api/matchday").json()
    assert day["matchday_number"] == 38 and day["last_matchday"] is True
    assert client.get("/api/table").json()["matchday_number"] == 38
    assert "the season's last" in channel_intro(38, True)
    midseason = channel_intro(12, False)
    assert "matchday 12" in midseason and "title" not in midseason
