"""How the final day unfolded: the recap the channel shows once the last match ends."""

from typing import Literal

from pydantic import Field

from app.models.common import Contract
from app.models.matchday import ClubRef
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
    """The day's story: written by the recap writer agent and checked (or by code, if every
    draft failed its checks or the agents are off), beside the outcomes code worked out."""

    status: RecapStatus = Field(
        description="pending: matches still playing; writing: the agent is on it; ready."
    )
    written_by: Literal["agents", "code"] | None = None
    headline: str | None = None
    standfirst: str | None = None
    beats: list[RecapBeat] = Field(default_factory=list)
    champions: ClubRef | None = None
    top_four: list[ClubRef] = Field(default_factory=list)
    relegated: list[ClubRef] = Field(default_factory=list)
    golden_boot: ScorerRow | None = None
    facts: list[RecapFact] = Field(default_factory=list)
    checks: list[str] = Field(
        default_factory=list, description="What the checkers sent back on the way, if anything."
    )
