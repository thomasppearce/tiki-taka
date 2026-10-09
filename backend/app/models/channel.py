"""The whip-around channel: which match is on air, the Director's next cut, and why."""

from typing import Literal

from pydantic import Field

from app.models.common import Contract, UnitInterval
from app.models.proposals import Claim

CutReason = Literal["kickoff", "goal", "pressure", "check_in", "manual"]
DecidedBy = Literal["code", "director", "producer"]


class SideSignal(Contract):
    club_id: str
    pressure: UnitInterval = Field(description="Something about to happen: recent threat, shots.")
    stake: float = Field(ge=0, description="What a goal for this side would change (table weight).")
    stake_summary: str | None = None


class MatchSignal(Contract):
    match_id: str
    home: SideSignal
    away: SideSignal
    score: float = Field(ge=0, description="How much the match deserves the screen right now.")


class CutPackage(Contract):
    """What the viewer is told when the feed cuts to a match."""

    why: str = Field(description="Why we're here.")
    at_stake: str | None = Field(description="What a goal here would change in the table.")
    story: str = Field(description="The story of this match so far.")
    claims: list[Claim]
    written_by: list[str] = Field(description="'code', or the agents that wrote it.")


class Cut(Contract):
    cut_id: str
    match_id: str
    clock_ms: int = Field(ge=0)
    reason: CutReason
    decided_by: DecidedBy
    package: CutPackage
    replay_event_id: str | None = Field(
        default=None, description="Open with a replay of this goal or chance."
    )


class PendingCut(Contract):
    """The Director's next cut, counting down. The producer can take it now or hold it."""

    match_id: str
    reason: CutReason
    proposed_ms: int = Field(ge=0)
    take_at_ms: int = Field(ge=0)
    package: CutPackage
    replay_event_id: str | None = None


LogAgent = Literal["director", "watcher", "checker", "producer", "code"]


class ChannelLog(Contract):
    """One line of the channel's log: who did what, when."""

    clock_ms: int = Field(ge=0)
    agent: LogAgent
    match_id: str | None = None
    detail: str


class Channel(Contract):
    clock_ms: int = Field(ge=0)
    version: int = Field(ge=0)
    on_air: Cut
    pending: PendingCut | None
    held: bool = Field(description="The producer has paused automatic cuts.")
    pinned_match_id: str | None = Field(description="The producer has fixed the feed on a match.")
    history: list[Cut] = Field(description="Earlier cuts, newest first.")
    signals: list[MatchSignal] = Field(description="Every live match, most deserving first.")
    log: list[ChannelLog] = Field(description="What the Director, Watchers, and producer did.")
    agents: bool = Field(description="The Watcher and Director agents are connected.")


class TakeRequest(Contract):
    """Take the pending cut now (no match_id), or cut straight to a match."""

    match_id: str | None = None


class HoldRequest(Contract):
    held: bool


class PinRequest(Contract):
    match_id: str | None = None
