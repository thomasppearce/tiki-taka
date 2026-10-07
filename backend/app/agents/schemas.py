"""What each agent returns. Every agent answers with structured output validated against these
models, so a malformed answer fails loudly instead of reaching the queue."""

from typing import Literal

from pydantic import BaseModel, Field

GraphicType = Literal["narrative_line", "tactical_insight", "stat_graphic", "player_tag"]


class Interpretation(BaseModel):
    """The Interpreter's read of a detected moment."""

    worth_airing: bool = Field(description="False only if a viewer would not care right now.")
    angle: str = Field(description="One sentence: why this moment matters in this match.")
    type: GraphicType
    focus_player_id: str | None = Field(
        default=None,
        description="The one player the graphic is about, if any (an id from the brief).",
    )


class DraftClaim(BaseModel):
    text: str = Field(description="One factual statement the graphic makes.")
    evidence_event_ids: list[str] = Field(description="Ids of the brief's events that prove it.")


class Draft(BaseModel):
    """The Explainer's graphic, in English."""

    headline: str = Field(description="At most 8 words.")
    body: str = Field(description="At most 30 words: what happened and why it matters.")
    claims: list[DraftClaim] = Field(description="Every factual statement, each with its evidence.")
    background_used: list[str] = Field(
        default_factory=list,
        description="Titles of the knowledge base sections the graphic draws on, if any.",
    )


class Placement(BaseModel):
    """The Producer's decision about the queue."""

    priority: float = Field(
        ge=0, le=1, description="How much it matters now, relative to the queue."
    )
    shelf_life_seconds: int = Field(ge=20, le=90, description="How long it stays relevant.")
    type: GraphicType
    reason: str = Field(description="One short sentence.")


class Localized(BaseModel):
    """The Localizer's variants: analyst and casual, English and Spanish."""

    analyst_headline_en: str
    analyst_body_en: str
    analyst_headline_es: str
    analyst_body_es: str
    casual_headline_en: str
    casual_body_en: str
    casual_headline_es: str
    casual_body_es: str
