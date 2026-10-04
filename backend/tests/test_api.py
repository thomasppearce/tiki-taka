"""The match centre, match detail, and live stream endpoints."""

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.live.clock import FULL_TIME_HOLD_MS, MatchdayClock
from app.main import app
from app.models import LiveEvent, Matchday, MatchDetail, TrackingFrame


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def at_minute(client: TestClient, minute: float, speed: float = 0) -> None:
    """Pin the matchday clock to a minute (speed 0 freezes it)."""
    service = client.app.state.matchday  # type: ignore[attr-defined]
    service.clock = MatchdayClock(service.clock.cycle_ms, start_minute=minute, speed=speed)


def test_matchday_lists_three_leagues_of_four(client: TestClient) -> None:
    at_minute(client, 63)
    day = Matchday.model_validate(client.get("/api/matchday").json())
    assert [len(league.matches) for league in day.leagues] == [4, 4, 4]
    featured = [m for league in day.leagues for m in league.matches if m.featured]
    assert [m.match_id for m in featured] == ["m_l1_1"]
    card = featured[0]
    assert (card.home.short, card.away.short) == ("NGR", "WMA")
    assert (card.score_home, card.score_away, card.status) == (1, 0, "live")
    assert len(card.momentum) == 64
    assert card.top_moment is not None


def test_match_detail_shows_only_what_has_happened(client: TestClient) -> None:
    at_minute(client, 63)
    detail = MatchDetail.model_validate(client.get("/api/matches/m_l1_1").json())
    assert detail.home_stats.goals == 1 and detail.away_stats.goals == 0
    assert len(detail.players) == 32
    assert all(e.match_clock_ms <= detail.card.clock_ms for e in detail.recent_events)
    assert all(k.match_clock_ms <= detail.card.clock_ms for k in detail.key_moments)
    assert [i.event_id for i in detail.impacts] == [e.event_id for e in detail.recent_events]


def test_finished_matches_hold_the_final_score(client: TestClient) -> None:
    at_minute(client, 97)
    detail = MatchDetail.model_validate(client.get("/api/matches/m_l1_1").json())
    assert detail.card.status == "full_time"
    assert (detail.card.score_home, detail.card.score_away) == (1, 2)


def test_unknown_match_is_404(client: TestClient) -> None:
    assert client.get("/api/matches/m_nope").status_code == 404


def test_stream_sends_frames_cards_and_events(client: TestClient) -> None:
    at_minute(client, 63, speed=40)  # 10 s of match time per frame, so events arrive
    with client.stream("GET", "/api/matches/m_l1_1/stream", params={"frames": 4}) as response:
        assert response.status_code == 200
        messages = _sse(response.iter_lines())
    kinds = [m["event"] for m in messages]
    assert kinds.count("frame") == 4
    assert "card" in kinds and "match_event" in kinds
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


def test_payloads_are_plain_json(client: TestClient) -> None:
    at_minute(client, 63)
    json.dumps(client.get("/api/matchday").json())
