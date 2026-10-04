"""Data contracts (CLAUDE.md section 5): the single source of truth for all shared types."""

from app.models.audit import AuditRecord
from app.models.events import EventAttributes, MatchEvent
from app.models.insight import EventImpact, KeyMoment, TeamStats
from app.models.live import LiveEvent
from app.models.matchday import Matchday, MatchDetail
from app.models.moments import Moment
from app.models.overlays import OverlayCommand
from app.models.proposals import AudienceBody, Claim, LocalizedText, Proposal
from app.models.tracking import PlayerPosition, TrackingFrame
from app.models.viewer import ViewerProfile

CONTRACTS = (
    MatchEvent,
    Moment,
    Proposal,
    OverlayCommand,
    AuditRecord,
    ViewerProfile,
    TrackingFrame,
    EventImpact,
    KeyMoment,
    TeamStats,
    Matchday,
    MatchDetail,
    LiveEvent,
)
"""Top-level contracts exported to JSON Schema and TypeScript."""

__all__ = [
    "CONTRACTS",
    "AudienceBody",
    "AuditRecord",
    "Claim",
    "EventAttributes",
    "EventImpact",
    "KeyMoment",
    "LiveEvent",
    "MatchDetail",
    "Matchday",
    "LocalizedText",
    "MatchEvent",
    "Moment",
    "OverlayCommand",
    "PlayerPosition",
    "Proposal",
    "TeamStats",
    "TrackingFrame",
    "ViewerProfile",
]
