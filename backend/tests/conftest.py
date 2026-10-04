"""Shared fixtures: one API client (and one simulated matchday) for the whole test session."""

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from app.live.clock import MatchdayClock
from app.live.service import MatchdayService
from app.main import app


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def service(client: TestClient) -> MatchdayService:
    return client.app.state.matchday  # type: ignore[attr-defined]


@pytest.fixture
def at_minute(service: MatchdayService) -> Callable[..., None]:
    """Pin the matchday clock to a minute (speed 0 freezes it)."""

    def pin(minute: float, speed: float = 0) -> None:
        service.clock = MatchdayClock(service.clock.cycle_ms, start_minute=minute, speed=speed)

    return pin
