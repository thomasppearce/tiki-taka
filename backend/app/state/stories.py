"""The players' stories in a match, as they stand at a moment: the Golden Boot race, a milestone
near or reached, a farewell, a player against his old club, a derby, a striker reaching double
figures. Written by code from the season (app/generator/player_season.py) and the day's events,
so the agents can use them as context and the checker can hold every number to them."""

from collections import Counter
from typing import TYPE_CHECKING

from app.generator.player_season import DERBIES, FAREWELLS, FORMER_CLUBS, MILESTONES
from app.state.scorers import Scorer, standings

if TYPE_CHECKING:
    from app.live.service import MatchdayService

BOOT_LEAD = 0.35  # a goal here would put a player top of the Golden Boot race (or further clear)
BOOT_LEVEL = 0.25  # ...or level at the top


def match_stories(service: "MatchdayService", match_id: str, t: int) -> list[str]:
    """Every player story in this match at `t`, most important first."""
    m = service.by_id[match_id]
    at = min(t, m.result.full_time_ms)
    goals = [e for e in m.result.events if e.type == "goal" and e.match_clock_ms <= at]
    scored = Counter(e.player_id for e in goals)
    first = {}  # each scorer's first goal today, for "his 100th (34')"
    for e in reversed(goals):
        first[e.player_id] = f"{e.match_clock_ms // 60_000 + 1}'"
    squads = {p.player_id for c in (m.home, m.away) for p in c.squad}
    playing = {p for p in squads if service.fantasy.on_pitch(p, at) or scored[p]}
    name = service.surname
    out: list[str] = []

    race = standings(service.season_goals, service.goal_list, t)  # the race now, not at FT
    lead = race[0][1].goals
    leaders = [s for _, s in race if s.goals == lead]
    out += [
        _boot_line(service, s, leaders)
        for _, s in race
        if s.player_id in playing and s.goals >= lead - 1
    ]
    for ms in MILESTONES:
        if ms.player_id in playing:
            club = service.club(_club_of(service, ms.player_id)).name
            now = ms.goals + scored[ms.player_id]
            short = ms.target - now
            out.append(
                f"{name(ms.player_id)}'s {first[ms.player_id]} goal is his {ms.target}th league "
                f"goal for {club}."
                if short <= 0
                else f"{name(ms.player_id)} is {_count(short)} short of {ms.target} league goals "
                f"for {club}."
            )
    for fw in FAREWELLS:
        if fw.player_id in squads:
            club = service.club(_club_of(service, fw.player_id)).name
            out.append(
                f"{name(fw.player_id)}'s last game: he retires after {fw.seasons} seasons at "
                f"{club}."
            )
    for fc in FORMER_CLUBS:
        if fc.player_id in squads and fc.former_club_id in (m.home.club_id, m.away.club_id):
            club = service.club(_club_of(service, fc.player_id)).name
            former = service.club(fc.former_club_id).name
            done = (
                f"scores against {former} ({first[fc.player_id]})" if scored[fc.player_id] else ""
            )
            out.append(
                f"{name(fc.player_id)} {done or f'faces {former}'}, the club he left for {club} "
                "last summer."
            )
    for d in DERBIES:
        if {d.home_id, d.away_id} == {m.home.club_id, m.away.club_id}:
            out.append(f"This is {d.name}: {m.home.name} v {m.away.name}.")
    # One striker a side chasing double figures: the one closest to goal in the side's attack.
    for club in (m.home, m.away):
        chasing = [
            p
            for p in club.squad
            if p.role == "fwd"
            and p.player_id in playing
            and service.player_seasons[p.player_id].goals == 9
        ]
        if chasing:
            # Who just reached it, else the likeliest to.
            p = max(chasing, key=lambda q: (scored[q.player_id] > 0, q.finishing)).player_id
            if scored[p]:
                out.append(f"{name(p)}'s {first[p]} goal is his 10th of the season.")
            else:
                out.append(f"{name(p)} is one goal from double figures for the season.")
    return out


def boot_stake(service: "MatchdayService", club_id: str, t: int) -> tuple[float, str | None]:
    """What a goal for `club_id` could do in the Golden Boot race: the best of its contenders on
    the pitch (one goal from the top or already there)."""
    race = standings(service.season_goals, service.goal_list, t)
    lead = race[0][1].goals
    leaders = {s.player_id for _, s in race if s.goals == lead}
    best: tuple[float, str | None] = (0.0, None)
    for _, s in race:
        if _club_of(service, s.player_id) != club_id or not service.fantasy.on_pitch(
            s.player_id, t
        ):
            continue
        who = service.surname(s.player_id)
        if s.goals == lead:
            weight = BOOT_LEAD
            phrase = (
                f"a goal from {who} extends his Golden Boot lead"
                if leaders == {s.player_id}
                else f"a goal from {who} puts him top of the Golden Boot race on {s.goals + 1}"
            )
        elif s.goals == lead - 1:
            weight = BOOT_LEVEL
            phrase = f"a goal from {who} draws him level at the top of the Golden Boot race"
        else:
            continue
        if weight > best[0]:
            best = (weight, phrase)
    return best


def _boot_line(service: "MatchdayService", s: Scorer, leaders: list[Scorer]) -> str:
    name = service.surname(s.player_id)
    others = [service.surname(x.player_id) for x in leaders if x.player_id != s.player_id]
    if s in leaders and not others:
        return f"{name} leads the Golden Boot race on {s.goals}."
    if s in leaders:
        return (
            f"{name} is level at the top of the Golden Boot race with {_and(others)}, on {s.goals}."
        )
    return f"{name} is one behind {_and(others)} in the Golden Boot race, on {s.goals}."


def _club_of(service: "MatchdayService", player_id: str) -> str:
    return service.fantasy.players[player_id][1].club_id


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}"


def _count(n: int) -> str:
    return {1: "one", 2: "two", 3: "three"}.get(n, str(n))
