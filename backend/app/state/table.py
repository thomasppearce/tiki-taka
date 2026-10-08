"""As it stands: the league table with today's scores added, and what each goal changes.

The final day is decided in the table, so this is what the whip-around runs on. Everything here
is code, not a model: the table, the swings (every goal that moved a club into or out of a zone,
with the goal's event id, so agents can cite it), and the stakes (for each live match, what one
more goal for either side would change right now). The Director weighs stakes as "does it
matter"; the swings are the day's story in order.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.generator.season import ZONES, Record, Zone, zone_of

# How much a zone change matters to the broadcast: the title and the drop most.
ZONE_WEIGHT: dict[Zone, float] = {"champions": 1.0, "relegation": 1.0, "continental": 0.5}

Scores = Mapping[str, tuple[int, int]]  # club_id -> (scored, conceded) today, as it stands


@dataclass(frozen=True)
class Placed:
    position: int
    record: Record  # including today's result as it stands

    @property
    def zone(self) -> Zone | None:
        return zone_of(self.position)


def standings(base: Sequence[Record], scores: Scores) -> list[Placed]:
    """The table as it stands: points, then goal difference, then goals scored."""
    records = [r.plus(*scores[r.club_id]) if r.club_id in scores else r for r in base]
    ordered = sorted(
        records, key=lambda r: (-r.points, -r.goal_difference, -r.goals_for, r.club_id)
    )
    return [Placed(i + 1, r) for i, r in enumerate(ordered)]


@dataclass(frozen=True)
class Change:
    club_id: str
    from_position: int
    to_position: int
    from_zone: Zone | None
    to_zone: Zone | None


def zone_changes(before: list[Placed], after: list[Placed]) -> list[Change]:
    """Clubs whose zone differs between two tables, most important first."""
    was = {p.record.club_id: p for p in before}
    changes = [
        Change(
            p.record.club_id,
            was[p.record.club_id].position,
            p.position,
            was[p.record.club_id].zone,
            p.zone,
        )
        for p in after
        if p.zone != was[p.record.club_id].zone
    ]
    return sorted(changes, key=lambda c: (-weight([c]), c.to_position))


def weight(changes: Sequence[Change]) -> float:
    """A swap of two clubs over a zone line counts once: the title or the drop 1, top four 0.5.
    Each club counts at its most important zone (top to second is the title, not top four)."""
    total = sum(max(ZONE_WEIGHT[z] for z in (c.from_zone, c.to_zone) if z) for c in changes)
    return round(total / 2, 2)


def summarize(changes: Sequence[Change], table: list[Placed], name: Mapping[str, str]) -> str:
    """One sentence for the changes, e.g. "Halvern Town go top on goal difference; Northgate
    Rovers drop to second." Written by code, so it can be shown and cited as is."""
    by_position = {p.position: p for p in table}
    parts = []
    for c in changes:
        phrase = _phrase(c)
        up = c.to_position < c.from_position
        # Goal difference decided it if the club is level on points with the one it passed.
        passed = by_position.get(c.to_position + 1 if up else c.to_position - 1)
        level = passed and passed.record.points == by_position[c.to_position].record.points
        moved_in = c.to_zone in ("champions", "continental") if up else c.to_zone == "relegation"
        if level and (moved_in or (up and c.from_zone == "relegation")):
            phrase += " on goal difference"
        parts.append(f"{name[c.club_id]} {phrase}")
    return "; ".join(parts) + "." if parts else ""


def _phrase(c: Change) -> str:
    up = c.to_position < c.from_position
    if c.to_zone == "champions":
        return "go top"
    if c.from_zone == "champions":
        return f"drop to {_ordinal(c.to_position)}"
    if c.to_zone == "relegation":
        return "drop into the relegation zone"
    if c.from_zone == "relegation":
        return "climb out of the relegation zone"
    if c.to_zone == "continental":
        return "move into the top four" if up else f"drop to {_ordinal(c.to_position)}"
    if c.from_zone == "continental":
        return "drop out of the top four"
    return f"move to {_ordinal(c.to_position)}"


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


__all__ = ["ZONES", "Change", "Placed", "standings", "summarize", "weight", "zone_changes"]
