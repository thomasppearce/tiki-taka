"""Aggregator outputs: what the raw events mean (importance, key moments, team stats).

These are deterministic facts computed from events with the expected-threat model, not agent
interpretations: the agents read them, and so do the match centre and the tactical view.
"""

from typing import Literal

from pydantic import Field

from app.models.common import Contract, UnitInterval

KeyMomentKind = Literal[
    "goal", "big_chance", "save", "red_card", "decisive_pass", "ball_won", "momentum_shift"
]


class EventImpact(Contract):
    """How much one action changed the game for the acting team."""

    event_id: str
    team_id: str | None = None
    threat: float = Field(description="Expected threat added (negative when possession is lost).")
    importance: UnitInterval


class KeyMoment(Contract):
    """A defining play, ranked by importance, with the events that make it up."""

    moment_id: str
    kind: KeyMomentKind
    match_clock_ms: int = Field(ge=0)
    team_id: str | None = None
    label: str = Field(description="Short English label, e.g. 'Goal: Kallo'.")
    importance: UnitInterval
    evidence_event_ids: list[str] = Field(min_length=1)


class TeamStats(Contract):
    team_id: str
    goals: int = Field(ge=0)
    shots: int = Field(ge=0)
    shots_on_target: int = Field(ge=0)
    xg: float = Field(ge=0)
    passes: int = Field(ge=0)
    pass_accuracy: UnitInterval
    possession_pct: float = Field(ge=0, le=100)
    field_tilt_pct: float = Field(
        ge=0, le=100, description="Share of both teams' final-third passes made by this team."
    )
    tackles: int = Field(ge=0)
    fouls: int = Field(ge=0)
    offsides: int = Field(ge=0)
    yellow_cards: int = Field(ge=0)
    red_cards: int = Field(ge=0)
