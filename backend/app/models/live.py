"""Payloads on a match's live stream."""

from app.models.common import Contract
from app.models.events import MatchEvent
from app.models.insight import EventImpact


class LiveEvent(Contract):
    """A match event as it happens, with how much it mattered."""

    event: MatchEvent
    impact: EventImpact
