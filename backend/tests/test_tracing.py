"""Each agent run is one span carrying the match and how it ended (app/agents/tracing.py), so
Foundry's trace list shows every run, cached or live, and the failures stand out."""

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from app.agents.channel_runner import ChannelRunner
from app.agents.schemas import StoryUpdate

EXPORTER = InMemorySpanExporter()


@pytest.fixture
def spans() -> InMemorySpanExporter:
    """Record spans in memory. OpenTelemetry takes one global provider per process, so the
    first test sets it and the rest reuse it."""
    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
        trace.set_tracer_provider(provider)
    EXPORTER.clear()
    return EXPORTER


class FakeTeam:
    """A Watcher that answers after one send-back, or fails outright."""

    model = "fake"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def story(self, brief: Any) -> tuple[StoryUpdate, int, list[str], list[str]]:
        if self.fail:
            raise RuntimeError("the model is down")
        return StoryUpdate(story="Level at the break.", claims=[]), 900, [], ["cited evt_9"]


class FakeChannel:
    def __init__(self) -> None:
        self.ready: list[str] = []
        self.failed: list[str] = []

    def story_ready(
        self, match_id: str, key: str, *args: Any, sent_back: Sequence[str] = ()
    ) -> None:
        self.ready.append(key)

    def story_failed(self, match_id: str, key: str, reason: str) -> None:
        self.failed.append(reason)


def _story(runner: ChannelRunner, channel: FakeChannel) -> ReadableSpan:
    asyncio.run(runner._story(channel, "m_l1_1", "m_l1_1:join55", None))  # type: ignore[arg-type]
    *_, span = EXPORTER.get_finished_spans()
    return span


def test_a_watcher_run_is_one_span_live_then_cached(
    tmp_path: Path, spans: InMemorySpanExporter
) -> None:
    runner, channel = ChannelRunner(FakeTeam(), cache_dir=tmp_path), FakeChannel()  # type: ignore[arg-type]
    live = _story(runner, channel)
    assert live.name == "watcher"
    assert live.attributes is not None
    assert live.attributes["tiki_taka.match_id"] == "m_l1_1"
    assert live.attributes["tiki_taka.status"] == "ready"
    assert live.attributes["tiki_taka.cached"] is False
    assert live.attributes["tiki_taka.sent_back"] == 1
    assert [e.name for e in live.events] == ["sent back by the checker"]
    assert live.status.status_code is StatusCode.UNSET

    cached = _story(runner, channel)  # the same story again: answered from the cache
    assert cached.attributes is not None
    assert cached.attributes["tiki_taka.cached"] is True
    assert cached.attributes["tiki_taka.status"] == "ready"
    assert channel.ready == ["m_l1_1:join55", "m_l1_1:join55"]


def test_a_failed_run_is_an_error_span_that_says_what_aired_instead(
    tmp_path: Path, spans: InMemorySpanExporter
) -> None:
    runner, channel = ChannelRunner(FakeTeam(fail=True), cache_dir=tmp_path), FakeChannel()  # type: ignore[arg-type]
    span = _story(runner, channel)
    assert span.status.status_code is StatusCode.ERROR
    assert span.status.description == "RuntimeError: the last story stands"
    assert channel.failed == ["RuntimeError"]
