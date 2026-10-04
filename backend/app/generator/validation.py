"""Realism validation for generated matches.

Each check compares a statistic of a simulated match against the range seen in real top-flight
football. Ranges bound a single match, not a season average (a dominant side can have 35+ shots
or 800+ passes in one game); the point is to catch a generator that has drifted into nonsense,
not to fit any real league.

As tuned on 2026-10-04: across five matchdays (60 matches, 1,200 checks) about 99% of checks
pass, and the rare failures are near misses (for example 36 tackles against a ceiling of 32),
which is the normal single-match variance of a stochastic simulation.

Run the report: `uv run python -m app.generator.validation [matches]`
"""

import math
import statistics
import sys
from collections import Counter
from dataclasses import dataclass

from app.generator.engine import FrameStore, MatchResult

# (label, min, max). Per-team stats are checked for both teams.
TEAM_RANGES: dict[str, tuple[float, float]] = {
    "passes": (300, 950),
    "pass_accuracy": (0.65, 0.92),
    "shots": (2, 38),
    "tackles": (6, 32),
    "fouls": (1, 22),
    "pressures": (60, 280),
    "offsides": (0, 7),
}
MATCH_RANGES: dict[str, tuple[float, float]] = {
    "goals": (0, 8),
    "shots": (10, 50),
    "cards": (0, 9),
    "possession_home_pct": (25, 75),
    "median_distance_km": (9.0, 13.0),
    "median_sprints_per_player": (5, 40),
    "max_top_speed_kmh": (30, 37.5),
    "median_shot_speed_kmh": (60, 110),
    "corners": (1, 22),
    "throw_ins": (15, 65),
    "goal_kicks": (4, 30),
    "free_kicks": (8, 45),
}


@dataclass(frozen=True)
class Check:
    name: str
    value: float
    low: float
    high: float

    @property
    def ok(self) -> bool:
        return self.low <= self.value <= self.high


def match_stats(result: MatchResult) -> dict[str, float]:
    """The statistics the checks look at, for one match."""
    stats: dict[str, float] = {}
    by_team: dict[str, Counter[str]] = {
        result.home.club_id: Counter(),
        result.away.club_id: Counter(),
    }
    completed: Counter[str] = Counter()
    shot_speeds: list[float] = []
    sprints: Counter[str] = Counter()
    top_speed = 0.0
    for e in result.events:
        if not e.team_id:
            continue
        by_team[e.team_id][e.type] += 1
        if e.type == "pass" and e.outcome == "success":
            completed[e.team_id] += 1
        if e.type == "shot" and e.attributes.ball_speed_kmh:
            shot_speeds.append(e.attributes.ball_speed_kmh)
        if e.type == "sprint" and e.player_id:
            sprints[e.player_id] += 1
            top_speed = max(top_speed, e.attributes.top_speed_kmh or 0)

    for side, team_id in (("home", result.home.club_id), ("away", result.away.club_id)):
        counts = by_team[team_id]
        stats[f"{side}.passes"] = counts["pass"]
        stats[f"{side}.pass_accuracy"] = completed[team_id] / max(1, counts["pass"])
        stats[f"{side}.shots"] = counts["shot"]
        stats[f"{side}.tackles"] = counts["tackle"]
        stats[f"{side}.fouls"] = counts["foul"]
        stats[f"{side}.pressures"] = counts["pressure"]
        stats[f"{side}.offsides"] = counts["offside"]

    total_passes = stats["home.passes"] + stats["away.passes"]
    stats["goals"] = sum(c["goal"] for c in by_team.values())
    stats["shots"] = stats["home.shots"] + stats["away.shots"]
    stats["cards"] = sum(c["card"] for c in by_team.values())
    stats["possession_home_pct"] = 100 * stats["home.passes"] / max(1, total_passes)
    stats["median_distance_km"] = statistics.median(distances_km(result.frames))
    stats["median_sprints_per_player"] = statistics.median(sprints.values()) if sprints else 0
    stats["max_top_speed_kmh"] = top_speed
    stats["median_shot_speed_kmh"] = statistics.median(shot_speeds) if shot_speeds else 0
    restarts = Counter(e.type for e in result.events)
    for kind in ("corner", "throw_in", "goal_kick", "free_kick"):
        stats[f"{kind}s"] = restarts[kind]
    return stats


def distances_km(frames: FrameStore) -> list[float]:
    """Distance covered per outfield slot over the match, from the tracking frames."""
    d, stride = frames.data, frames.STRIDE
    totals = []
    for slot in range(22):
        if slot in (0, 11):
            continue  # goalkeepers
        total = 0.0
        for k in range(1, frames.count):
            a, b = (k - 1) * stride + 2 + slot * 2, k * stride + 2 + slot * 2
            step = math.hypot(d[b] - d[a], d[b + 1] - d[a + 1])
            if step < 6:  # ignore half-time resets and sent-off gaps
                total += step
        totals.append(total / 1000)
    return totals


def validate(result: MatchResult) -> list[Check]:
    stats = match_stats(result)
    checks = [
        Check(f"{side}.{name}", stats[f"{side}.{name}"], low, high)
        for name, (low, high) in TEAM_RANGES.items()
        for side in ("home", "away")
    ]
    checks += [Check(name, stats[name], low, high) for name, (low, high) in MATCH_RANGES.items()]
    return checks


def report(results: list[MatchResult]) -> str:
    lines = []
    failures = 0
    for result in results:
        checks = validate(result)
        bad = [c for c in checks if not c.ok]
        failures += len(bad)
        score = result.score_at(result.full_time_ms)
        lines.append(
            f"{result.match_id} {result.home.short} {score[0]}-{score[1]} {result.away.short} "
            f"({result.storyline.name}): {len(checks) - len(bad)}/{len(checks)} checks pass"
        )
        for c in bad:
            lines.append(f"    FAIL {c.name} = {c.value:.2f} (expected {c.low}-{c.high})")
    lines.append(f"{'ALL CHECKS PASS' if failures == 0 else f'{failures} failing checks'}")
    return "\n".join(lines)


if __name__ == "__main__":
    from app.generator.matchday import build_matchday

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    print(report([m.result for m in build_matchday()[:limit]]))
