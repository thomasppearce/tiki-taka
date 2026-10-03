"""5.4 OverlayCommand: the timed, machine-readable instruction emitted on approval."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.common import Audience, Contract, Language

OverlayTemplate = Literal[
    "lower_third", "stat_bar", "player_tag", "momentum_graph", "scorebug_update"
]

AnimationIn = Literal["slide_up", "fade", "wipe"]

AnimationOut = Literal["fade", "slide_down", "wipe"]


class OverlayStat(Contract):
    label: str
    value: str


class OverlayPayload(Contract):
    headline: str
    body: str | None = None
    stats: list[OverlayStat] = Field(default_factory=list)
    player_id: str | None = None
    spotlight: OverlayStat | None = Field(
        default=None, description="The feed's spotlight metric (ViewerProfile.spotlight_metric)."
    )


class OverlayStyle(Contract):
    theme: str = "default"
    animation_in: AnimationIn = "slide_up"
    animation_out: AnimationOut = "fade"


class OverlayCommand(Contract):
    """Rendered for one output feed: `profile_id` names the ViewerProfile it was made for."""

    overlay_id: str
    proposal_id: str
    profile_id: str
    template: OverlayTemplate
    start_clock_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)
    audience: Audience
    language: Language
    payload: OverlayPayload
    style: OverlayStyle = Field(default_factory=OverlayStyle)
    approved_by: str
    approved_at: datetime
