"""The failure drill: make an agent fail on purpose and watch the system recover."""

from typing import Literal

from pydantic import Field

from app.models.common import Contract

DrillAgent = Literal[
    "interpreter", "explainer", "fact_checker", "producer", "localizer", "watcher", "director"
]
DrillMode = Literal["blip", "down"]


class DrillRequest(Contract):
    """Start a drill: `blip` fails the agent's next model call once (the retry recovers it);
    `down` fails every call for a few minutes (the system falls back)."""

    agent: DrillAgent
    mode: DrillMode


class DrillState(Contract):
    """The drill now: which agent is failing and how, or none."""

    agent: DrillAgent | None = None
    mode: DrillMode | None = None
    seconds_left: int = Field(default=0, ge=0, description="Until a `down` drill ends by itself.")
