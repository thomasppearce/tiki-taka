"""The SSE endpoint streams valid, deterministic match events."""

from collections.abc import Iterator

from fastapi.testclient import TestClient

from app.generator.fake import FULL_TIME_MS, fake_events
from app.main import app
from app.models import MatchEvent


def parse_sse(lines: Iterator[str]) -> list[dict[str, str]]:
    """Group SSE lines into messages; a blank line ends a message, `:` lines are comments."""
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


def test_stream_emits_match_events() -> None:
    client = TestClient(app)
    params = {"limit": 5, "interval_ms": 0}
    with client.stream("GET", "/api/stream/events", params=params) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        messages = parse_sse(response.iter_lines())

    assert len(messages) == 5
    for message in messages:
        event = MatchEvent.model_validate_json(message["data"])
        assert message["event"] == "match_event"
        assert message["id"] == event.event_id


def test_fake_match_is_deterministic_and_ends_at_full_time() -> None:
    first, second = list(fake_events(seed=3)), list(fake_events(seed=3))
    assert first == second
    assert first[0].type == "kickoff"
    assert all(e.match_clock_ms < FULL_TIME_MS for e in first)
    clocks = [e.match_clock_ms for e in first]
    assert clocks == sorted(clocks)


def test_health() -> None:
    assert TestClient(app).get("/api/health").json() == {"status": "ok"}
