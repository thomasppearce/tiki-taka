"""5.3 Proposal: a candidate graphic or line waiting in the producer's queue."""

from typing import Literal

from pydantic import Field

from app.models.common import Contract, UnitInterval

ProposalType = Literal[
    "stat_graphic", "narrative_line", "tactical_insight", "player_tag", "recap_beat"
]

ProposalStatus = Literal["pending", "approved", "edited", "rejected", "expired"]

AgentName = Literal[
    "interpreter",
    "explainer",
    "checker",
    "fact_checker",
    "producer",
    "localizer",
    "renderer",
    "orchestrator",
]


class LocalizedText(Contract):
    """One piece of copy per supported language. English is always present."""

    en: str = Field(min_length=1)
    es: str | None = None


class AudienceBody(Contract):
    """The same insight written for each audience."""

    analyst: LocalizedText
    casual: LocalizedText


class Claim(Contract):
    """A factual statement made by a proposal. Every claim cites the events that support it."""

    text: str = Field(min_length=1)
    evidence_event_ids: list[str] = Field(min_length=1)


class Proposal(Contract):
    """A candidate graphic or line. It must make at least one cited claim: no narration without
    receipts. `headline` and `body` are both written per audience and language."""

    proposal_id: str
    moment_id: str
    type: ProposalType
    priority: UnitInterval
    confidence: UnitInterval
    expires_at_clock_ms: int = Field(ge=0)
    headline: AudienceBody
    body: AudienceBody
    claims: list[Claim] = Field(min_length=1)
    status: ProposalStatus = "pending"
    produced_by: list[AgentName] = Field(default_factory=list)
    trace_id: str | None = None
    player_id: str | None = Field(
        default=None, description="The player this is about; drives player tags and player focus."
    )
