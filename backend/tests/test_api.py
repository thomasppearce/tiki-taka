"""The match centre, match detail, and live stream endpoints."""

import json
from collections.abc import Callable, Iterator

from fastapi.testclient import TestClient

from app.live.clock import FULL_TIME_HOLD_MS, QUIET_RESTART_S, MatchdayClock
from app.models import Desk, LiveEvent, Matchday, MatchDetail, TrackingFrame

Pin = Callable[..., None]


def test_matchday_is_one_league_of_ten(client: TestClient, at_minute: Pin) -> None:
    at_minute(63)
    day = Matchday.model_validate(client.get("/api/matchday").json())
    assert [len(league.matches) for league in day.leagues] == [10]
    featured = [m for league in day.leagues for m in league.matches if m.featured]
    assert [m.match_id for m in featured] == ["m_l1_1"]
    card = featured[0]
    assert (card.home.short, card.away.short) == ("NGR", "WMA")
    assert (card.score_home, card.score_away, card.status) == (1, 0, "live")
    assert len(card.momentum) == 64
    assert card.top_moment is not None


def test_match_detail_shows_only_what_has_happened(client: TestClient, at_minute: Pin) -> None:
    at_minute(63)
    detail = MatchDetail.model_validate(client.get("/api/matches/m_l1_1").json())
    assert detail.home_stats.goals == 1 and detail.away_stats.goals == 0
    assert len(detail.players) == 32
    assert all(e.match_clock_ms <= detail.card.clock_ms for e in detail.recent_events)
    assert all(k.match_clock_ms <= detail.card.clock_ms for k in detail.key_moments)
    assert [i.event_id for i in detail.impacts] == [e.event_id for e in detail.recent_events]


def test_finished_matches_hold_the_final_score(client: TestClient, at_minute: Pin) -> None:
    at_minute(97)
    detail = MatchDetail.model_validate(client.get("/api/matches/m_l1_1").json())
    assert detail.card.status == "full_time"
    assert (detail.card.score_home, detail.card.score_away) == (1, 2)


def test_unknown_match_is_404(client: TestClient) -> None:
    assert client.get("/api/matches/m_nope").status_code == 404


def test_stream_sends_frames_cards_events_and_the_desk(client: TestClient, at_minute: Pin) -> None:
    at_minute(63, speed=40)  # 10 s of match time per frame, so events arrive
    with client.stream("GET", "/api/matches/m_l1_1/stream", params={"frames": 4}) as response:
        assert response.status_code == 200
        messages = _sse(response.iter_lines())
    kinds = [m["event"] for m in messages]
    assert kinds.count("frame") == 4
    assert "card" in kinds and "match_event" in kinds and "desk" in kinds
    Desk.model_validate_json(next(m for m in messages if m["event"] == "desk")["data"])
    frame = TrackingFrame.model_validate_json(
        next(m for m in messages if m["event"] == "frame")["data"]
    )
    assert len(frame.players) >= 20
    live = LiveEvent.model_validate_json(
        next(m for m in messages if m["event"] == "match_event")["data"]
    )
    assert live.impact.event_id == live.event.event_id


def test_clock_loops_and_holds_full_time() -> None:
    now = [0.0]
    clock = MatchdayClock(cycle_ms=95 * 60_000, start_minute=90, speed=1, now=lambda: now[0])
    assert clock.clock_ms() == 90 * 60_000
    now[0] = 5 * 60  # five minutes later: still inside the full-time hold
    assert clock.clock_ms() == 95 * 60_000
    now[0] = 5 * 60 + FULL_TIME_HOLD_MS / 1000  # the loop has kicked off again
    assert clock.clock_ms() == 0


def test_clock_starts_afresh_after_a_quiet_spell() -> None:
    now = [0.0]
    clock = MatchdayClock(cycle_ms=95 * 60_000, start_minute=55, speed=1, now=lambda: now[0])
    now[0] = 9 * 60
    assert clock.clock_ms() == 64 * 60_000  # someone is watching
    now[0] += QUIET_RESTART_S  # a long pause, but the clock was read just now
    assert clock.clock_ms() == 74 * 60_000
    now[0] += QUIET_RESTART_S + 1  # nobody read it for over ten minutes: as after a cold start
    assert clock.clock_ms() == 55 * 60_000


def _sse(lines: Iterator[str]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in lines:
        if not line:
            if current:
                messages.append(current)
            current = {}
        elif not line.startswith(":"):
            field, _, value = line.partition(":")
            current[field] = value.removeprefix(" ")
    if current:
        messages.append(current)
    return messages


def test_payloads_are_plain_json(client: TestClient, at_minute: Pin) -> None:
    at_minute(63)
    json.dumps(client.get("/api/matchday").json())


def test_events_by_id_returns_receipts_but_never_the_future(
    client: TestClient, at_minute: Pin
) -> None:
    at_minute(63)
    detail = MatchDetail.model_validate(client.get("/api/matches/m_l1_1").json())
    cited = [e for k in detail.key_moments for e in k.evidence_event_ids][:30]
    response = client.get("/api/matches/m_l1_1/events", params={"ids": ",".join(cited)})
    assert response.status_code == 200
    assert sorted(e["event_id"] for e in response.json()) == sorted(set(cited))
    at_minute(10)
    later = client.get("/api/matches/m_l1_1/events", params={"ids": ",".join(cited)}).json()
    assert all(e["match_clock_ms"] <= 10 * 60_000 for e in later)
