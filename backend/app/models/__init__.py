"""Data contracts (CLAUDE.md section 5): the single source of truth for all shared types."""

from app.models.audit import AuditRecord
from app.models.channel import Channel, HoldRequest, PinRequest, TakeRequest
from app.models.desk import ApproveRequest, Desk, OnAir
from app.models.events import EventAttributes, MatchEvent
from app.models.insight import EventImpact, KeyMoment, TeamStats
from app.models.live import LiveEvent
from app.models.matchday import Matchday, MatchDetail
from app.models.moments import Moment
from app.models.overlays import OverlayCommand
from app.models.proposals import AudienceBody, Claim, LocalizedText, Proposal
from app.models.replay import Replay
from app.models.table import LeagueTable
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
    Desk,
    ApproveRequest,
    LeagueTable,
    Channel,
    TakeRequest,
    HoldRequest,
    PinRequest,
    Replay,
)
"""Top-level contracts exported to JSON Schema and TypeScript."""

__all__ = [
    "CONTRACTS",
    "ApproveRequest",
    "AudienceBody",
    "AuditRecord",
    "Channel",
    "HoldRequest",
    "PinRequest",
    "TakeRequest",
    "Claim",
    "Desk",
    "EventAttributes",
    "EventImpact",
    "KeyMoment",
    "LiveEvent",
    "MatchDetail",
    "Matchday",
    "LeagueTable",
    "LocalizedText",
    "MatchEvent",
    "Moment",
    "OnAir",
    "OverlayCommand",
    "PlayerPosition",
    "Proposal",
    "Replay",
    "TeamStats",
    "TrackingFrame",
    "ViewerProfile",
]
