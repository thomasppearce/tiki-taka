"""Expected threat (xT): how likely possession in each pitch zone leads to a goal.

The grid is learned from our own simulated matches with the standard value-iteration method:
for each zone, count how often the team in possession shoots, scores, and moves the ball (by pass
or carry) to each other zone, then iterate

    xT(z) = P(shot | z) * P(goal | shot, z) + P(move | z) * sum over z' of T(z -> z') * xT(z')

until it converges. Coordinates are in the attacking team's frame: x from its own goal (0) to the
opponent's (100), y across the pitch (0-100), the same normalized units as MatchEvent.

Regenerate the committed grid: `uv run python -m app.state.xt`
"""

import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from app.models import MatchEvent

COLS, ROWS = 16, 12
GRID_PATH = Path(__file__).with_name("xt_grid.json")
TRAINING_SEEDS = range(9000, 9024)
SHOT_PRIOR_WEIGHT = 4.0  # shots of pseudo-evidence from the location xG model per zone


def to_frame(point: tuple[float, float], attacking_home: bool) -> tuple[float, float]:
    """Normalized pitch coordinates into the attacking team's frame."""
    x, y = point
    return (x, y) if attacking_home else (100 - x, 100 - y)


def zone(x: float, y: float) -> int:
    col = min(COLS - 1, max(0, int(x / 100 * COLS)))
    row = min(ROWS - 1, max(0, int(y / 100 * ROWS)))
    return row * COLS + col


@dataclass(frozen=True)
class XTGrid:
    values: tuple[float, ...]  # ROWS x COLS, row-major

    def at(self, x: float, y: float) -> float:
        """xT at a point in the attacking team's frame."""
        return self.values[zone(x, y)]


@cache
def load_grid() -> XTGrid:
    data = json.loads(GRID_PATH.read_text())
    return XTGrid(tuple(v for row in data["values"] for v in row))


def learn(matches: list[tuple[list[MatchEvent], str]], iterations: int = 60) -> list[float]:
    """Learn xT from (events, home_team_id) pairs."""
    cells = COLS * ROWS
    actions = [0.0] * cells
    shots = [0.0] * cells
    goals = [0.0] * cells
    moves = [0.0] * cells
    transitions: list[dict[int, float]] = [{} for _ in range(cells)]

    for events, home_id in matches:
        receiver: tuple[str, int] | None = None  # (player_id, zone) after a completed pass
        for e in events:
            if e.type not in ("pass", "shot") or not e.location or not e.team_id:
                if e.type in (
                    "tackle",
                    "foul",
                    "offside",
                    "throw_in",
                    "goal_kick",
                    "corner",
                    "free_kick",
                    "penalty",
                    "kickoff",
                    "save",
                    "half_end",
                    "goal",
                ):
                    receiver = None
                continue
            home = e.team_id == home_id
            z = zone(*to_frame((e.location.x, e.location.y), home))
            # The receiver carried the ball from where they got it to where they acted.
            if receiver and receiver[0] == e.player_id:
                actions[receiver[1]] += 1
                moves[receiver[1]] += 1
                transitions[receiver[1]][z] = transitions[receiver[1]].get(z, 0) + 1
            receiver = None
            actions[z] += 1
            if e.type == "shot":
                shots[z] += 1
                goals[z] += 1 if e.outcome == "goal" else 0
                continue
            moves[z] += 1
            if e.outcome == "success" and e.end_location and e.target_player_id:
                z_end = zone(*to_frame((e.end_location.x, e.end_location.y), home))
                transitions[z][z_end] = transitions[z].get(z_end, 0) + 1
                receiver = (e.target_player_id, z_end)

    shoot_p = [shots[z] / actions[z] if actions[z] else 0.0 for z in range(cells)]
    move_p = [moves[z] / actions[z] if actions[z] else 0.0 for z in range(cells)]
    goal_p = [
        (goals[z] + SHOT_PRIOR_WEIGHT * _prior(z)) / (shots[z] + SHOT_PRIOR_WEIGHT)
        for z in range(cells)
    ]
    xt = [0.0] * cells
    for _ in range(iterations):
        xt = [
            shoot_p[z] * goal_p[z]
            + (
                move_p[z] * sum(n / moves[z] * xt[t] for t, n in transitions[z].items())
                if moves[z]
                else 0.0
            )
            for z in range(cells)
        ]
    return _smooth(_symmetrize(xt, actions), actions)


def _mirror(z: int) -> int:
    return (ROWS - 1 - z // COLS) * COLS + z % COLS


def _symmetrize(xt: list[float], actions: list[float]) -> list[float]:
    """Football is left-right symmetric: pool each zone with its mirror, weighted by evidence."""
    out = []
    for z in range(len(xt)):
        m = _mirror(z)
        total = actions[z] + actions[m]
        out.append((xt[z] * actions[z] + xt[m] * actions[m]) / total if total else 0.0)
    return out


def _smooth(xt: list[float], actions: list[float], weight: float = 25.0) -> list[float]:
    """Pull zones with little evidence toward the mean of their neighbours."""
    out = []
    for z in range(len(xt)):
        col, row = z % COLS, z // COLS
        neighbours = [
            xt[r * COLS + c]
            for r in range(max(0, row - 1), min(ROWS, row + 2))
            for c in range(max(0, col - 1), min(COLS, col + 2))
            if (r, c) != (row, col)
        ]
        mean = sum(neighbours) / len(neighbours)
        evidence = actions[z] + actions[_mirror(z)]
        out.append((xt[z] * evidence + mean * weight) / (evidence + weight))
    return out


def _prior(z: int) -> float:
    """Location xG at the zone's centre, used to steady sparse zones."""
    from app.generator.engine import expected_goals

    col, row = z % COLS, z // COLS
    x = (col + 0.5) / COLS * 105
    y = (row + 0.5) / ROWS * 68
    return expected_goals(math.hypot(105 - x, 34 - y), abs(math.atan2(y - 34, 105 - x)))


def _training_matches() -> list[tuple[list[MatchEvent], str]]:
    """Unscripted (balanced) matches across the league's clubs, separate from the final day."""
    from app.generator.engine import MatchEngine
    from app.generator.storylines import STORYLINES
    from app.generator.world import build_world

    clubs = [club for league in build_world() for club in league.clubs]
    matches = []
    for i, seed in enumerate(TRAINING_SEEDS):
        home, away = clubs[i % len(clubs)], clubs[(i + 5) % len(clubs)]
        result = MatchEngine(f"m_train_{i}", home, away, STORYLINES["balanced"], seed).run()
        matches.append((result.events, home.club_id))
    return matches


if __name__ == "__main__":
    training = _training_matches()
    values = learn(training)
    actions = sum(1 for events, _ in training for e in events if e.type in ("pass", "shot"))
    GRID_PATH.write_text(
        json.dumps(
            {
                "cols": COLS,
                "rows": ROWS,
                "trained_on": f"{len(training)} simulated balanced matches, seeds "
                f"{TRAINING_SEEDS.start}-{TRAINING_SEEDS.stop - 1}, {actions} passes and shots",
                "values": [
                    [round(values[r * COLS + c], 4) for c in range(COLS)] for r in range(ROWS)
                ],
            },
            indent=1,
        )
        + "\n"
    )
    print(f"Wrote {GRID_PATH} from {len(training)} matches ({actions} actions)")
    for r in range(ROWS):
        print(" ".join(f"{values[r * COLS + c]:.3f}" for c in range(COLS)))
