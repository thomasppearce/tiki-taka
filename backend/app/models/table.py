"""The live league table: the final day's scores added to the season so far, as it stands."""

from typing import Literal

from pydantic import Field

from app.models.common import Contract
from app.models.matchday import ClubRef

Zone = Literal["champions", "continental", "relegation"]
Result = Literal["winning", "drawing", "losing"]


class TableRow(Contract):
    position: int = Field(ge=1)
    club: ClubRef
    played: int = Field(ge=0)
    won: int = Field(ge=0)
    drawn: int = Field(ge=0)
    lost: int = Field(ge=0)
    goals_for: int = Field(ge=0)
    goals_against: int = Field(ge=0)
    goal_difference: int
    points: int = Field(ge=0)
    zone: Zone | None
    start_position: int = Field(ge=1, description="Position before today's kickoff.")
    match_id: str = Field(description="Today's match.")
    result: Result = Field(description="Today's match as it stands (or as it ended).")


class ZoneChange(Contract):
    """One club moving into or out of a zone."""

    club_id: str
    from_position: int = Field(ge=1)
    to_position: int = Field(ge=1)
    from_zone: Zone | None
    to_zone: Zone | None


class TableSwing(Contract):
    """A goal that changed the table's zones: who moved where. Written by code, citable."""

    match_clock_ms: int = Field(ge=0)
    match_id: str
    event_id: str = Field(description="The goal.")
    changes: list[ZoneChange]
    summary: str = Field(description="One sentence, e.g. 'Halvern Town go top on goal difference.'")


class Stake(Contract):
    """What one more goal for one side in one live match would change in the table right now."""

    match_id: str
    scorer_club_id: str
    changes: list[ZoneChange]
    summary: str
    weight: float = Field(
        ge=0, description="How much the change matters: title and drop 1, top four 0.5."
    )


class LeagueTable(Contract):
    clock_ms: int = Field(ge=0)
    rows: list[TableRow]
    swings: list[TableSwing] = Field(description="Every zone change so far today, oldest first.")
    stakes: list[Stake] = Field(description="For each live match and side, what a goal would do.")
