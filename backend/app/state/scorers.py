"""The Golden Boot as it stands: the season's goals plus today's, and every goal that changed who
leads the race. Code, not a model, like the table (table.py): the agents cite it as written."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

TOP = 5  # positions shown (more rows when players are level)
WAYS = {3: "three", 4: "four", 5: "five"}


@dataclass(frozen=True)
class Scorer:
    player_id: str
    season: int  # before today
    today: int

    @property
    def goals(self) -> int:
        return self.season + self.today


@dataclass(frozen=True)
class Swing:
    clock_ms: int
    match_id: str
    event_id: str
    player_id: str
    summary: str


def standings(
    season: Mapping[str, int], goals: Sequence[tuple[int, str, str, str]], t: int, top: int = TOP
) -> list[tuple[int, Scorer]]:
    """The race at `t`, as (position, scorer); `goals` are (clock, match, event, scorer) in time
    order. Players level share a position, and everyone level with the last place shown is in."""
    today: dict[str, int] = {}
    for clock, _, _, player_id in goals:
        if clock > t:
            break
        today[player_id] = today.get(player_id, 0) + 1
    totals = {p: season.get(p, 0) + n for p, n in today.items()}
    totals.update({p: g for p, g in season.items() if p not in totals})
    ranked = sorted(totals, key=lambda p: (-totals[p], p))
    rows: list[tuple[int, Scorer]] = []
    for i, p in enumerate(ranked):
        position = rows[-1][0] if rows and rows[-1][1].goals == totals[p] else i + 1
        if position > top:
            break
        rows.append((position, Scorer(p, season.get(p, 0), today.get(p, 0))))
    return rows


def swings(
    season: Mapping[str, int],
    goals: Sequence[tuple[int, str, str, str]],
    names: Mapping[str, str],
) -> list[Swing]:
    """Every goal that changed the top of the race: a new leader, or a player drawing level."""
    totals = dict(season)
    out = []
    for clock, match_id, event_id, player_id in goals:
        before = max(totals.values())
        leaders_before = {p for p, g in totals.items() if g == before}
        totals[player_id] = totals.get(player_id, 0) + 1
        mine = totals[player_id]
        top = max(totals.values())
        if mine < top:
            continue
        leaders = sorted((p for p, g in totals.items() if g == top), key=lambda p: names[p])
        name = names[player_id]
        if len(leaders) == 1:
            if leaders_before == {player_id}:
                summary = f"{name} extends his lead in the Golden Boot race to {mine}."
            else:
                summary = f"{name} goes top of the Golden Boot race on {mine}."
        else:
            others = [names[p] for p in leaders if p != player_id]
            level = others[0] if len(others) == 1 else ", ".join(others[:-1]) + f" and {others[-1]}"
            if len(leaders) == 2:
                summary = (
                    f"{name} draws level with {level} at the top of the Golden Boot race, "
                    f"on {mine}."
                )
            else:
                summary = (
                    f"{name} makes it a {WAYS.get(len(leaders), len(leaders))}-way tie at the top "
                    "of the Golden Boot race, "
                    f"with {level}, on {mine}."
                )
        out.append(Swing(clock, match_id, event_id, player_id, summary))
    return out
