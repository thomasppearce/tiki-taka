"""What each agent returns. Every agent answers with structured output validated against these
models, so a malformed answer fails loudly instead of reaching the queue."""

from typing import Literal

from pydantic import BaseModel, Field

GraphicType = Literal["narrative_line", "tactical_insight", "stat_graphic", "player_tag"]


class Interpretation(BaseModel):
    """The Interpreter's read of a detected moment."""

    worth_airing: bool = Field(description="False only if a viewer would not care right now.")
    angle: str = Field(description="One sentence: why this moment matters in this match.")
    evidence_event_ids: list[str] = Field(
        default_factory=list, description="Ids of the brief's events the angle rests on."
    )
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


Verdict = Literal["supported", "fair reading", "unsupported", "wrong"]


class StatementCheck(BaseModel):
    statement: str = Field(description="One statement from the headline or body, quoted.")
    verdict: Verdict = Field(
        description="supported: the brief states it. fair reading: it follows directly from the "
        "brief's events, score, or stats. unsupported: the brief doesn't show it. wrong: the "
        "brief shows otherwise."
    )
    brief_shows: str = Field(description="What the brief shows about it, in a few words.")


class FactCheck(BaseModel):
    """The fact-checker's verdict on each statement in a graphic."""

    statements: list[StatementCheck] = Field(
        description="Every statement in the headline and body, in order, each with a verdict."
    )

    @property
    def problems(self) -> list[str]:
        """The statements that send the draft back: unsupported or wrong."""
        return [
            f'"{s.statement}" is {s.verdict}: the brief shows {s.brief_shows}'
            for s in self.statements
            if s.verdict in ("unsupported", "wrong")
        ]


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


class StoryUpdate(BaseModel):
    """A Watcher's story of its match so far, for a viewer cutting in."""

    story: str = Field(description="At most 35 words: the story of this match so far.")
    claims: list[DraftClaim] = Field(description="Every factual statement, each with its evidence.")


class CutDecision(BaseModel):
    """The Director's choice of where to cut, and what to say as we arrive."""

    match_id: str = Field(description="The id of the candidate to cut to.")
    why: str = Field(description="At most 18 words: why we are going there right now.")
    at_stake: str | None = Field(
        description="At most 25 words, from that candidate's AT STAKE lines; null if none."
    )
    claims: list[DraftClaim] = Field(description="Every factual statement, each with its evidence.")


class RecapBeatDraft(BaseModel):
    minute: int = Field(description="The minute it happened, as its facts give it.")
    text: str = Field(description="At most 30 words.")
    fact_ids: list[str] = Field(description="Ids of the facts it rests on.")


class RecapDraft(BaseModel):
    """The recap writer's story of the day."""

    headline: str = Field(description="At most 10 words.")
    standfirst: str = Field(
        description="At most 45 words: how the title, the top four, the relegation places, and "
        "the Golden Boot were settled."
    )
    beats: list[RecapBeatDraft] = Field(
        description="Four to six moments that decided the day, in time order."
    )
