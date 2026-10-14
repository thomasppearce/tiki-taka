"""The whip-around channel: which match is on air, the Director's next cut, and why."""

from typing import Literal

from pydantic import Field

from app.models.common import Contract, UnitInterval
from app.models.matchday import PlayerRef, Role
from app.models.proposals import Claim

CutReason = Literal["kickoff", "goal", "penalty", "pressure", "check_in", "manual"]
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
    for_you: str | None = Field(
        default=None, description="On a personal whip-around: what this match means to you."
    )
    storyline: str | None = Field(
        default=None,
        description="A player's story here (the Golden Boot race, a milestone...), by code.",
    )


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


LensKind = Literal["channel", "club", "fantasy"]


class FantasyItem(Contract):
    """One line of a fantasy player's score, with the events that earned it."""

    label: str
    points: int
    event_ids: list[str]


class FantasyPlayer(Contract):
    player_id: str
    name: str
    number: int
    role: Role
    club_id: str
    match_id: str
    on_pitch: bool = Field(description="On the pitch now (or at full time).")
    points: int
    items: list[FantasyItem]


class Lens(Contract):
    """Whose whip-around this is: everyone's channel, a fan's club, or a fan's fantasy XI."""

    kind: LensKind
    club_id: str | None = None
    xi: list[FantasyPlayer] = Field(default_factory=list, description="With live points.")
    points: int = Field(default=0, description="The fantasy XI's total, as it stands.")


class Squads(Contract):
    """Every player in the league, for picking a fantasy XI, and a suggested XI."""

    players: list[PlayerRef]
    suggested_xi: list[str]
    rules: list[str] = Field(description="How fantasy points are scored, one rule per line.")


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
    lens: Lens


class TakeRequest(Contract):
    """Take the pending cut now (no match_id), or cut straight to a match."""

    match_id: str | None = None


class HoldRequest(Contract):
    held: bool


class PinRequest(Contract):
    match_id: str | None = None


class ClockRequest(Contract):
    """Move the matchday clock (a demo control): `minute` as the scorebug shows it, or None for
    the moment the day's last match ends."""

    minute: float | None = Field(default=None, ge=0)
