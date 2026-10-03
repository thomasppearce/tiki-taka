"""5.6 ViewerProfile: how one output feed is personalized."""

from typing import Literal

from pydantic import Field

from app.models.common import Audience, Contract, Language

SpotlightMetric = Literal[
    "pass_accuracy", "pass_difficulty", "distance_covered", "top_speed", "shot_speed", "pressures"
]


class ViewerProfile(Contract):
    """Setting `focus_player_id` turns on player-focus mode for the feed."""

    profile_id: str
    audience: Audience
    language: Language = "en"
    favorite_club_id: str | None = None
    favorite_player_ids: list[str] = Field(default_factory=list)
    focus_player_id: str | None = None
    spotlight_metric: SpotlightMetric | None = Field(
        default=None, description="The single performance metric this viewer cares about."
    )
