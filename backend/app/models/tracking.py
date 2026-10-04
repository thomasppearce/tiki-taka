"""5.7 TrackingFrame: synthetic tracking data, every player and the ball at one instant."""

from pydantic import Field

from app.models.common import Contract, PitchPoint


class PlayerPosition(Contract):
    """One player's position. Players can stand just off the pitch (throw-ins), hence the margin."""

    player_id: str
    team_id: str
    x: float = Field(ge=-5, le=105)
    y: float = Field(ge=-5, le=105)
    speed_kmh: float | None = Field(default=None, ge=0)


class TrackingFrame(Contract):
    """All 22 players and the ball at one match-clock instant. Streamed alongside MatchEvents so
    the control room can draw formations moving in sync with the actions."""

    match_id: str
    match_clock_ms: int = Field(ge=0)
    ball: PitchPoint
    players: list[PlayerPosition] = Field(min_length=1)
