"""Shared fixtures: one API client (and one simulated matchday) for the whole test session."""

import os
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

# Tests never call Foundry: the featured match uses the scripted producer unless a test wires a
# fake team in itself.
os.environ["TIKITAKA_AGENTS"] = "off"

from app.live.clock import MatchdayClock  # noqa: E402
from app.live.service import MatchdayService  # noqa: E402
from app.main import app  # noqa: E402


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
