"""5.2 Moment: a key moment detected by the Interpreter."""

from typing import Literal

from pydantic import Field

from app.models.common import Contract

MomentKind = Literal[
    "momentum_shift",
    "pressure_spike",
    "milestone",
    "tactical_change",
    "key_chance",
    "control_vs_chaos",
    "player_threshold",
]


class Moment(Contract):
    """Something worth surfacing, grounded in the events that triggered it."""

    moment_id: str
    kind: MomentKind
    match_clock_ms: int = Field(ge=0)
    summary: str = Field(min_length=1)
    metrics: dict[str, float] = Field(default_factory=dict)
    evidence_event_ids: list[str] = Field(min_length=1)
