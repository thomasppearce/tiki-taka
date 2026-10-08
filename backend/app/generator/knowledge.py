"""Write the generated part of the knowledge corpus: one page per club, the season so far, and
the laws the engine enforces. The Explainer agent retrieves these (Azure AI Search), so its
tactical claims rest on the same profiles and rules the matches were played with.

Every word here is original to this project, and every club and player is fictional.

Regenerate: `uv run python -m app.generator.knowledge [output_dir]` (default: ../knowledge)
"""

import sys
from pathlib import Path

from app.generator import engine
from app.generator.matchday import FIXTURES
from app.generator.season import ZONES, table_before_final_day
from app.generator.tactics import STYLE_NAMES, STYLE_SUMMARIES, describe
from app.generator.world import Club, League, build_world

ROLE_NAMES = {"gk": "Goalkeeper", "def": "Defender", "mid": "Midfielder", "fwd": "Forward"}


def club_page(club: Club, league: League) -> str:
    t = club.tactics
    rows = "\n".join(
        f"| {label} | {phrase} | {getattr(t, field):.2f} |"
        for (label, phrase), field in zip(
            describe(t),
            (
                "line_height",
                "press_height",
                "press_intensity",
                "width",
                "compactness",
                "tempo",
                "directness",
                "offside_trap",
                "runs_in_behind",
            ),
            strict=True,
        )
    )
    squad = "\n".join(
        f"| {p.number} | {p.name} | {ROLE_NAMES[p.role]} | {'Starter' if i < 11 else 'Bench'} |"
        for i, p in enumerate(club.squad)
    )
    return f"""# {club.name} ({club.short})

A fictional club in the {league.name}. Formation: {club.formation}. Style: {STYLE_NAMES[t.style]}.

## How they play

{STYLE_SUMMARIES[t.style]}

| Aspect | Setting | Dial (0 to 1) |
|---|---|---|
{rows}

## What to watch for

{_watch_for(club)}

## Squad

| No. | Player | Position | Role |
|---|---|---|---|
{squad}
"""


def _watch_for(club: Club) -> str:
    t = club.tactics
    notes = []
    if t.line_height > 0.65 and t.offside_trap > 0.6:
        notes.append(
            "A high line that steps up together catches runners offside, but a well-timed run "
            "or a ball over the top can leave the keeper exposed."
        )
    if t.line_height < 0.4:
        notes.append(
            "A deep line leaves little space in behind, so opponents have to break them down "
            "in front of the box; shots from range and crosses become the main threats."
        )
    if t.press_intensity > 0.7:
        notes.append(
            "They win the ball high up the pitch, so turnovers near the opponent's box are a "
            "major source of their chances."
        )
    if t.runs_in_behind > 0.7:
        notes.append(
            "Their forwards attack the space behind the defence constantly; expect sprints, "
            "through balls, and the occasional offside flag."
        )
    if t.directness > 0.7:
        notes.append("They move the ball forward quickly and do not mind losing it in the process.")
    if t.directness < 0.3:
        notes.append("They keep the ball patiently and can dominate possession without shooting.")
    return (
        " ".join(notes) or "They have no extreme tendencies; the game state shapes how they play."
    )


def laws_page() -> str:
    stoppages = "\n".join(
        f"| {kind.replace('_', ' ').capitalize()} | {low // 1000}-{high // 1000} s |"
        for kind, (low, high) in engine.STOPPAGE_MS.items()
    )
    return f"""# The laws the match engine enforces

These are the rules every simulated Match Desk match is played under. They follow the spirit of
the real laws of the game, simplified where the simulation needs it.

## Offside

- A player is in an offside position if, when a teammate passes to them, they are in the
  opponent's half and nearer the goal line than both the ball and the second-last opponent
  (usually the last outfield defender, with the keeper behind).
- Level is onside. The engine flags a player only when they are more than
  {engine.OFFSIDE_TOLERANCE_M:.2f} m beyond the line, the smallest margin an assistant would see.
- Offside is judged at the moment the pass is played, not where the ball is received.
- There is no offside from a throw-in, a goal kick, or a corner.
- An offside is punished with a free kick to the defending side where the offside player stood.
- Forwards wait about {engine.HOLD_LINE_M:.1f} m onside, then time their runs; a run released
  late, or a defensive line stepping up together, is what gets them caught.

## Restarts and stoppages

The ball is dead while a restart is set up: nobody presses or tackles until it is taken. The ball
is fetched to the restart spot and the taker walks to it; nobody is moved instantly. With these
stoppages, the ball is in play for roughly 60 of the 90-odd minutes, as in real football.

| Restart | Ball dead for |
|---|---|
{stoppages}
| Kickoff after a goal | {engine.GOAL_PAUSE_MS // 1000} s |

- A ball that crosses a touchline is a throw-in to the side that did not touch it last.
- A ball that crosses the goal line off an attacker is a goal kick; off a defender, a corner.
- Shots saved or blocked are sometimes turned behind for a corner, and crosses cleared near the
  goal line sometimes go behind for one too.
- A foul is a free kick where it happened, and may bring a yellow or red card.
- Substitutions are made during stoppages and add time to them.
- Keepers holding the ball in their own penalty area cannot be challenged.
- When a scripted storyline goal is still due at full time, the referee adds up to
  {engine.MAX_ADDED_MS // 60_000} minutes.
"""


def season_page(league: League) -> str:
    """The table going into the final day, and the races it sets up."""
    clubs = {c.club_id: c for c in league.clubs}
    table = table_before_final_day()
    rows = "\n".join(
        f"| {i} | {clubs[r.club_id].name} | {r.played} | {r.won} | {r.drawn} | {r.lost} | "
        f"{r.goals_for} | {r.goals_against} | {r.goal_difference:+d} | {r.points} |"
        for i, r in enumerate(table, start=1)
    )
    by_short = {clubs[r.club_id].short: (i, r) for i, r in enumerate(table, start=1)}

    def club(short: str) -> str:
        position, r = by_short[short]
        return (
            f"{clubs[r.club_id].name} ({_ordinal(position)}, {r.points} points, "
            f"goal difference {r.goal_difference:+d})"
        )

    first, second = (by_short[s][1] for s in ("NGR", "HVT"))
    safe, drop = (by_short[s][1] for s in ("WMA", "CRB"))
    top, bottom = ZONES["relegation"]
    fixtures = "\n".join(
        f"- {_name(clubs, home)} v {_name(clubs, away)}" for home, away, _ in FIXTURES
    )
    return f"""# The {league.name}: the season so far

## Overview

The {league.name} is a fictional league of {len(league.clubs)} clubs, each playing 38 games.
After 37 rounds, everything that matters is still to be decided on the final day, when all ten
matches kick off at the same time. The champions finish first, the continental cup places are
{_ordinal(ZONES["continental"][0])} to {_ordinal(ZONES["continental"][1])}, and the bottom
three ({_ordinal(top)} to {_ordinal(bottom)}) are relegated. Clubs level on points are separated
by goal difference, then goals scored.

## The table going into the final day

| Pos | Club | P | W | D | L | GF | GA | GD | Pts |
|---|---|---|---|---|---|---|---|---|---|
{rows}

## The title race

{club("NGR")} lead {club("HVT")} by {first.points - second.points} points.
Halvern's goal difference is {second.goal_difference - first.goal_difference} better, so if
Northgate fail to win and Halvern win, Halvern are champions. Northgate host Westmere Athletic;
Halvern travel to Brackenford FC.

## The relegation battle

{_name(clubs, "DHU")} and {_name(clubs, "LPT")} are already relegated. The last relegation place
is between {club("WMA")} and {club("CRB")}. Westmere are {safe.points - drop.points} points
ahead, but Corrin Bay's goal difference is {drop.goal_difference - safe.goal_difference} better,
so a Corrin Bay win and a Westmere draw would send Westmere down. Westmere play the leaders,
Northgate Rovers; Corrin Bay host Millbrook Town.

## The race for fourth

{club("TDR")}, {club("KRC")}, and {club("PHA")} are chasing the last continental cup place.
{club("GHV")} have third secured.

## Final-day fixtures

{fixtures}
"""


def _name(clubs: dict[str, Club], short: str) -> str:
    return clubs[f"t_{short.lower()}"].name


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def main(out: Path) -> None:
    clubs_dir = out / "clubs"
    clubs_dir.mkdir(parents=True, exist_ok=True)
    pages = set()
    for league in build_world():
        for club in league.clubs:
            page = clubs_dir / f"{club.short.lower()}.md"
            page.write_text(club_page(club, league))
            pages.add(page)
    for stale in set(clubs_dir.glob("*.md")) - pages:  # clubs no longer in the world
        stale.unlink()
    count = len(pages)
    (league,) = build_world()
    (out / "season.md").write_text(season_page(league))
    (out / "laws-of-the-engine.md").write_text(laws_page())
    print(f"Wrote {count} club pages, the season page, and the laws page to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parents[3] / "knowledge")
