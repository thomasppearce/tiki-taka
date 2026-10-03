"""5.1 MatchEvent: one synthetic match event, as emitted by the generator."""

from typing import Literal, Self

from pydantic import Field, model_validator

from app.models.common import Contract, PitchPoint, UnitInterval

EventType = Literal[
    "pass",
    "shot",
    "tackle",
    "possession_change",
    "pressure",
    "foul",
    "card",
    "substitution",
    "goal",
    "save",
    "sprint",
    "kickoff",
    "half_end",
]

Outcome = Literal["success", "fail", "blocked", "saved", "off_target", "goal"]


class EventAttributes(Contract):
    """Measurements attached to an event. Which ones are set depends on the event type."""

    pass_distance_m: float | None = Field(default=None, ge=0)
    pass_difficulty: UnitInterval | None = None
    ball_speed_kmh: float | None = Field(
        default=None, ge=0, description="Ball speed; on shots this is the shot speed."
    )
    pressure_level: UnitInterval | None = None
    player_speed_kmh: float | None = Field(
        default=None, ge=0, description="The acting player's speed at the moment of the event."
    )
    distance_covered_m: float | None = Field(
        default=None, ge=0, description="The acting player's cumulative distance this match."
    )
    top_speed_kmh: float | None = Field(default=None, ge=0)
    sprint_distance_m: float | None = Field(default=None, ge=0)


REQUIRED_ATTRIBUTES: dict[str, tuple[str, ...]] = {
    "pass": ("pass_distance_m", "pass_difficulty"),
    "shot": ("ball_speed_kmh",),
    "sprint": ("top_speed_kmh", "sprint_distance_m"),
}
"""Attributes the challenge brief needs on every event of a given type."""


class MatchEvent(Contract):
    """A single timed event in a synthetic match."""

    event_id: str
    match_id: str
    minute: int = Field(ge=0, le=130)
    second: int = Field(ge=0, le=59)
    match_clock_ms: int = Field(ge=0)
    type: EventType
    team_id: str | None = None
    player_id: str | None = None
    target_player_id: str | None = None
    location: PitchPoint | None = None
    end_location: PitchPoint | None = None
    outcome: Outcome | None = None
    attributes: EventAttributes = Field(default_factory=EventAttributes)

    @model_validator(mode="after")
    def _require_type_attributes(self) -> Self:
        missing = [
            name
            for name in REQUIRED_ATTRIBUTES.get(self.type, ())
            if getattr(self.attributes, name) is None
        ]
        if missing:
            raise ValueError(f"{self.type} events require attributes: {', '.join(missing)}")
        return self
