"""A signed-in fan's own whip-around: their club or their fantasy XI decides what matters. The
cuts, the lines "for you", and every fantasy point, each with its receipts."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.generator.season import TEAM_OF_THE_SEASON
from app.live.service import MatchdayService

Pin = Callable[..., None]
WESTMERE = "club:t_wma"
XI = "xi:" + ",".join(TEAM_OF_THE_SEASON)
FULL_TIME = 99 * 60_000


def test_fantasy_points_have_receipts(service: MatchdayService) -> None:
    desai = service.fantasy.score("p_wma_09", FULL_TIME)  # two goals, the second the 94' winner
    assert desai.points == 2 + 4 + 4
    goals = [i for i in desai.items if i.label == "Goal"]
    assert len(goals) == 2 and all(len(i.event_ids) == 1 for i in goals)
    sato = service.fantasy.score("p_wma_08", FULL_TIME)  # set up the equaliser
    assist = next(i for i in sato.items if i.label == "Assist")
    assert assist.points == 3 and goals[0].event_ids[0] in assist.event_ids
    keeper = service.fantasy.score("p_dhu_01", FULL_TIME)
    assert {i.label for i in keeper.items} >= {"Clean sheet", "12 saves"}
    early = service.fantasy.score("p_wma_09", 30 * 60_000)  # nothing after the minute leaks out
    assert early.points == 1 and early.on_pitch


def test_an_xi_must_follow_the_rules(service: MatchdayService) -> None:
    assert service.fantasy.check_xi(list(TEAM_OF_THE_SEASON)) == []
    keepers = [*TEAM_OF_THE_SEASON[:10], "p_ngr_01"]  # a second keeper for a forward
    assert any("goalkeeper" in p for p in service.fantasy.check_xi(keepers))
    westmere = [p for p in TEAM_OF_THE_SEASON if p != "p_elr_11"] + ["p_wma_10"]
    assert service.fantasy.check_xi(westmere) == []  # three from a club is fine...
    four = [p for p in westmere if p != "p_lpt_09"] + ["p_wma_11"]
    assert "At most 3 from Westmere Athletic." in service.fantasy.check_xi(four)  # ...four isn't


def test_a_club_fan_hears_what_each_match_means_to_them(service: MatchdayService) -> None:
    whip = service.whip(WESTMERE)
    t = 56 * 60_000
    assert whip.lens.for_you("m_l1_3", t) == (
        "A goal for Millbrook Town: Westmere Athletic climb out of the relegation zone."
    )
    assert "Westmere Athletic's match" in (whip.lens.for_you("m_l1_1", t) or "")
    assert whip.lens.for_you("m_l1_2", t) is None  # the title race doesn't move Westmere
    signal = next(x for x in whip.signals(t) if x.match_id == "m_l1_3")
    assert signal.away.stake == 1.0 and signal.home.stake == 0.0


def test_only_goals_that_matter_cut_a_fans_whip_around(service: MatchdayService) -> None:
    whip = service.whip(WESTMERE)
    goal_cuts = set()
    for t in range(0, FULL_TIME, 1_000):
        whip.sync(t)
        assert whip.state
        if whip.state.pending and whip.state.pending.reason == "goal":
            goal_cuts.add((whip.state.pending.match_id, whip.state.pending.proposed_ms // 60_000))
    # Corrin Bay's 33' goal drops Westmere into the zone; Halvern's 79' title goal moves nothing.
    assert ("m_l1_3", 32) in goal_cuts
    assert all(match_id in ("m_l1_1", "m_l1_3") for match_id, _ in goal_cuts)


def test_a_fantasy_whip_around_follows_the_xi(service: MatchdayService) -> None:
    whip = service.whip(XI)
    assert service.whip(XI) is whip  # one Director per XI, however many tabs follow it
    snapshot = whip.snapshot(97 * 60_000)
    assert snapshot.lens.kind == "fantasy" and len(snapshot.lens.xi) == 11
    assert snapshot.lens.points == sum(p.points for p in snapshot.lens.xi)
    assert whip.lens.for_you("m_l1_1", FULL_TIME) == "Your XI here: Desai 10 pts, Sato 5 pts."
    blackwood = next(g for _, _, g in whip.goals if service.surname(g.player_id) == "Blackwood")
    assert whip.lens.goal_weight("m_l1_10", blackwood) == 1.0
    ambrose = next(g for _, _, g in whip.goals if service.surname(g.player_id) == "Ambrose")
    assert whip.lens.goal_weight("m_l1_2", ambrose) == 0.0  # not ours, and ours scored it


def test_the_api_serves_a_fans_whip_around(client: TestClient, at_minute: Pin) -> None:
    at_minute(56)
    channel = client.get("/api/channel", params={"lens": WESTMERE}).json()
    assert channel["lens"] == {"kind": "club", "club_id": "t_wma", "xi": [], "points": 0}
    assert channel["on_air"]["package"]["for_you"]
    assert client.get("/api/channel").json()["lens"]["kind"] == "channel"
    bad = client.get("/api/channel", params={"lens": "xi:p_ngr_01,p_ngr_02"})
    assert bad.status_code == 400 and "11" in bad.json()["detail"]
    assert client.get("/api/channel", params={"lens": "club:t_nope"}).status_code == 400
    main = client.get("/api/channel").json()["on_air"]["cut_id"]
    taken = client.post("/api/channel/take", params={"lens": XI}, json={"match_id": "m_l1_8"})
    assert taken.json()["on_air"]["match_id"] == "m_l1_8"
    assert client.get("/api/channel").json()["on_air"]["cut_id"] == main  # the fan's cut only
    squads = client.get("/api/squads").json()
    assert len(squads["players"]) == 20 * 16 and squads["suggested_xi"] == list(TEAM_OF_THE_SEASON)
    assert squads["rules"]


def test_a_fans_whip_around_keeps_the_watchers_running(service: MatchdayService) -> None:
    whip = service.whip("club:t_crb")
    whip.sync(40 * 60_000)
    assert service.channel.state and service.channel.state.clock_ms == 40 * 60_000
