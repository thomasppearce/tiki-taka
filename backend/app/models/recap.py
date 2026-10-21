"""How a matchday unfolded: the recap the channel shows once the day's last match ends."""

from typing import Literal

from pydantic import Field

from app.models.common import Contract
from app.models.matchday import ClubRef
from app.models.proposals import Claim
from app.models.table import ScorerRow

RecapStatus = Literal["pending", "writing", "ready"]


class RecapFact(Contract):
    """One fact written by code: an outcome, a goal that moved the table or the Golden Boot, or
    a final score. The recap's beats cite these by id."""

    fact_id: str = Field(
        description="A goal ('<match_id>:<event_id>'), a final score ('ft:<match_id>'), or an "
        "outcome ('final:<what>')."
    )
    minute: int | None = None
    match_id: str | None = None
    text: str


class RecapBeat(Contract):
    minute: int = Field(ge=0)
    match_id: str | None = None
    text: str
    fact_ids: list[str] = Field(description="The facts this beat rests on.")


class Recap(Contract):
    """How a matchday unfolded: written by the recap writer agent and checked (or by code, if
    every draft failed its checks or the agents are off), beside where code says the day left
    the table. On the season's last matchday that is how the season ended."""

    status: RecapStatus = Field(
        description="pending: matches still playing; writing: the agent is on it; ready."
    )
    matchday: int | None = Field(default=None, ge=1)
    season_over: bool = Field(
        default=False, description="The season's last matchday: the top is the champions."
    )
    written_by: Literal["agents", "code"] | None = None
    headline: str | None = None
    standfirst: str | None = None
    beats: list[RecapBeat] = Field(default_factory=list)
    top: ClubRef | None = None
    top_four: list[ClubRef] = Field(default_factory=list)
    bottom_three: list[ClubRef] = Field(
        default_factory=list, description="The relegation places: relegated, if the season is over."
    )
    golden_boot: ScorerRow | None = Field(default=None, description="The leader (the winner).")
    facts: list[RecapFact] = Field(default_factory=list)
    checks: list[str] = Field(
        default_factory=list, description="What the checkers sent back on the way, if anything."
    )


class MatchRecap(Contract):
    """One match's recap at its final whistle: written by its Watcher and checked (or by code,
    from its goals, if every draft failed its checks or the agents are off)."""

    match_id: str
    status: RecapStatus
    home: ClubRef
    away: ClubRef
    score_home: int = Field(ge=0, description="The final score.")
    score_away: int = Field(ge=0)
    written_by: Literal["agents", "code"] | None = None
    headline: str | None = None
    story: str | None = None
    claims: list[Claim] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)


class YourDay(Contract):
    """A fan's own matchday beside the recap, written by code from the same facts: what the day
    did to their club (its result, where it finished, the goals that moved it), or how their
    fantasy XI scored. A guest gets the recap alone."""

    status: RecapStatus = Field(description="pending until the day's last match ends.")
    kind: Literal["club", "fantasy"] | None = None
    club: ClubRef | None = None
    headline: str | None = None
    lines: list[RecapFact] = Field(
        default_factory=list, description="Each with the goal or result behind it."
    )
    points: int | None = Field(default=None, description="The fantasy XI's total.")
