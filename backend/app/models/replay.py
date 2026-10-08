"""A replay: the frames and events of the move behind a goal or a big chance."""

from typing import Literal

from pydantic import Field

from app.models.common import Contract
from app.models.events import MatchEvent
from app.models.tracking import TrackingFrame


class Replay(Contract):
    match_id: str
    event_id: str = Field(description="The goal or shot replayed.")
    kind: Literal["goal", "chance"]
    label: str = Field(description="One line, e.g. 'Ambrose scores for Halvern Town'.")
    as_it_stands: str | None = Field(
        default=None,
        description="What the goal changed in the table, e.g. 'As it stands: Halvern Town go top'.",
    )
    from_ms: int = Field(ge=0)
    to_ms: int = Field(ge=0)
    slow_from_ms: int = Field(ge=0, description="Slow motion from here...")
    slow_to_ms: int = Field(ge=0, description="...to here: the shot.")
    shooter_id: str | None = None
    frames: list[TrackingFrame] = Field(description="Every 250 ms across the window.")
    events: list[MatchEvent] = Field(description="The events in the window, oldest first.")
