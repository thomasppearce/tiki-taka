"""The proposal desk for one match: what is pending, what is on air, and the decision log."""

from pydantic import Field

from app.models.audit import AuditRecord
from app.models.common import Contract
from app.models.overlays import OverlayTemplate
from app.models.proposals import Proposal


class OnAir(Contract):
    """An approved graphic on air. Each viewer renders it for their own feed profile."""

    proposal: Proposal
    template: OverlayTemplate
    start_clock_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)
    approved_by: str


class Desk(Contract):
    match_id: str
    version: int = Field(ge=0)
    clock_ms: int = Field(ge=0)
    proposals: list[Proposal]  # pending, highest priority first
    on_air: OnAir | None = None
    audit: list[AuditRecord]  # newest first
    aired: int = Field(ge=0)
    rejected: int = Field(ge=0)
    expired: int = Field(ge=0)


class ApproveRequest(Contract):
    """Approve a proposal, optionally editing its copy for one feed's audience and language."""

    profile_id: str = "feed_analyst_en"
    headline: str | None = None
    body: str | None = None
