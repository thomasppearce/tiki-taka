"""A fan's own matchday, beside the recap: what the day did to their club, or how their fantasy
XI scored. Written by code from the final table, the day's swings, and the fantasy scores, so
every line is a fact with the goal or result behind it; no model writes it."""

from typing import TYPE_CHECKING

from app.live.lens import ClubLens, FantasyLens, lens_for
from app.models.channel import FantasyPlayer
from app.models.recap import RecapFact, YourDay
from app.models.table import LeagueTable, TableRow, Zone
from app.state.table import zone_of

if TYPE_CHECKING:
    from app.live.service import MatchdayService

MAX_PLAYERS = 5  # the XI's best performers, one line each


def your_day(service: "MatchdayService", lens_key: str | None, ended: bool, now: int) -> YourDay:
    """`lens_key` as the channel takes it ("club:<id>" or "xi:<ids>"); anything else, or the
    main channel, has no day of its own."""
    if not ended and now < service.over_ms:
        return YourDay(status="pending")
    lens = lens_for(service, lens_key)
    table = service.table_at(service.over_ms)
    if isinstance(lens, ClubLens):
        return _club_day(service, lens, table)
    if isinstance(lens, FantasyLens):
        return _fantasy_day(service, lens)
    return YourDay(status="ready")


def _club_day(service: "MatchdayService", lens: ClubLens, table: LeagueTable) -> YourDay:
    row = next(r for r in table.rows if r.club.club_id == lens.club_id)
    m = service.by_id[lens.match_id]
    home, away = m.result.score_at(m.result.full_time_ms)
    goals = [e for e in m.result.events if e.type == "goal"]
    minutes: dict[str, list[str]] = {}  # each scorer once: "Desai 73', 93'"
    for e in goals:
        minutes.setdefault(service.surname(e.player_id), []).append(
            f"{e.match_clock_ms // 60_000 + 1}'"
        )
    scorers = "; ".join(f"{name} {', '.join(at)}" for name, at in minutes.items())
    result = f"{m.home.name} {home}-{away} {m.away.name}" + (f": {scorers}." if goals else ".")
    zones = {zone_of(row.start_position)} | {
        z
        for swing in table.swings
        for c in swing.changes
        if c.club_id == lens.club_id
        for z in (c.from_zone, c.to_zone)
    }
    # In time order: the goals that moved them, then their result (at full time), then where
    # they finished.
    lines = [
        RecapFact(
            fact_id=f"{swing.match_id}:{swing.event_id}",
            minute=swing.match_clock_ms // 60_000 + 1,
            match_id=swing.match_id,
            text=swing.summary,
        )
        for swing in table.swings
        if any(c.club_id == lens.club_id for c in swing.changes)
    ]
    lines.append(RecapFact(fact_id=f"ft:{m.match_id}", match_id=m.match_id, text=result))
    start = _ordinal(row.start_position)
    end = _ordinal(row.position)
    moved = f"from {start} to {end}" if start != end else f"{end}, where they started the day"
    lines.append(
        RecapFact(
            fact_id="final:position",
            text=f"{lens.name} finish {moved}, on {row.points} points.",
        )
    )
    return YourDay(
        status="ready",
        kind="club",
        club=row.club,
        headline=_club_headline(lens.name, row, zones, table.last_matchday),
        lines=lines,
    )


def _club_headline(name: str, row: TableRow, zones: set[Zone | None], last: bool) -> str:
    """What the day meant for the club, the biggest change first. `zones`: every zone it was
    in at some point today (Westmere spent an hour in the drop zone, then stayed up)."""
    after = row.zone
    top_four = ("champions", "continental")
    if after == "champions":
        return f"{name} are champions" if last else f"{name} end the day top"
    if "champions" in zones:
        return f"{name} miss out on the title" if last else f"{name} lose top spot"
    if after == "relegation":
        return f"{name} are relegated" if last else f"{name} end the day in the drop zone"
    if "relegation" in zones:
        return f"{name} stay up" if last else f"{name} climb out of the drop zone"
    if after in top_four and zone_of(row.start_position) not in top_four:
        return f"{name} make the top four"
    if after not in top_four and any(z in top_four for z in zones):
        return f"{name} miss out on the top four"
    return f"{name} finish {_ordinal(row.position)}"


def _fantasy_day(service: "MatchdayService", lens: FantasyLens) -> YourDay:
    info = lens.info(service.over_ms)
    best = sorted(info.xi, key=lambda p: (-p.points, p.name))
    lines = [_player_line(service, p) for p in best[:MAX_PLAYERS] if p.points > 0]
    headline = f"Your XI scored {info.points} points"
    if best and best[0].points > 0:
        headline += f": {best[0].name.split(' ', 1)[-1]} led with {best[0].points}"
    return YourDay(
        status="ready", kind="fantasy", headline=headline, lines=lines, points=info.points
    )


def _player_line(service: "MatchdayService", player: FantasyPlayer) -> RecapFact:
    counts: dict[str, int] = {}
    for item in player.items:
        counts[item.label] = counts.get(item.label, 0) + 1
    parts = []
    for label, n in counts.items():
        if label.startswith("Playing"):
            continue
        noun = label.lower()
        parts.append(
            f"{n} {noun}s" if n > 1 else (f"a {noun}" if noun[0] not in "0123456789" else noun)
        )
    club = service.club(player.club_id).short
    text = f"{player.name} ({club}): {player.points} pts" + (
        f", {', '.join(parts)}." if parts else "."
    )
    # A line covers the player's whole day (four goals), so it has no one minute; it cites the
    # first event that earned points.
    cited = next((i.event_ids[0] for i in player.items if i.event_ids), None)
    return RecapFact(
        fact_id=f"{player.match_id}:{cited}" if cited else f"ft:{player.match_id}",
        match_id=player.match_id,
        text=text,
    )


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
