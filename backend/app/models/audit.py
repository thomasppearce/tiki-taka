"""5.5 AuditRecord: one entry in the decision log behind every proposal."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.models.common import Contract

AuditAction = Literal[
    "handoff", "created", "approved", "edited", "rejected", "expired", "agent_failure", "retry"
]

ActorType = Literal["agent", "human", "system"]


class AuditRecord(Contract):
    """A state change, who made it, and what it changed."""

    audit_id: str
    timestamp: datetime
    match_clock_ms: int | None = Field(default=None, ge=0)
    action: AuditAction
    actor_type: ActorType
    actor: str
    proposal_id: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    detail: str | None = None
