"""The expected-threat model and the aggregator built on it."""

from app.generator.matchday import FEATURED_MATCH_ID, build_matchday
from app.state.aggregator import event_impacts, key_moments, momentum, team_stats
from app.state.xt import COLS, ROWS, load_grid


def featured():
    match = next(m for m in build_matchday() if m.match_id == FEATURED_MATCH_ID)
    return match.result, match.home.club_id


def test_threat_rises_toward_goal_and_is_symmetric() -> None:
    grid = load_grid()
    assert grid.at(5, 50) < grid.at(50, 50) < grid.at(80, 50) < grid.at(97, 50)
    assert grid.at(97, 50) > grid.at(97, 5)  # central beats wide near goal
    for row in range(ROWS):
        for col in range(COLS):
            assert grid.values[row * COLS + col] == grid.values[(ROWS - 1 - row) * COLS + col]
    assert all(0 < v < 0.5 for v in grid.values)


def test_forward_passes_add_threat_and_backward_ones_barely_matter() -> None:
    result, home = featured()
    impacts = event_impacts(result.events, home)
    passes = [e for e in result.events if e.type == "pass" and e.outcome == "success"]
    forward = [p for p in passes if impacts[p.event_id].threat > 0.01]
    backward = [p for p in passes if impacts[p.event_id].threat < -0.005]
    assert forward and backward
    assert min(impacts[p.event_id].importance for p in forward) > max(
        impacts[p.event_id].importance for p in backward
    )


def test_momentum_stays_in_range_and_tracks_the_storyline() -> None:
    result, home = featured()
    impacts = event_impacts(result.events, home)
    curve = momentum(result.events, impacts, home, result.full_time_ms)
    assert len(curve) == result.full_time_ms // 60_000 + 1
    assert all(-1 <= v <= 1 for v in curve)
    # Westmere (away) dominate after the break in the comeback storyline.
    assert sum(curve[60:90]) < sum(curve[0:30])


def test_key_moments_include_every_goal_with_its_shot_as_evidence() -> None:
    result, home = featured()
    impacts = event_impacts(result.events, home)
    moments = key_moments(
        result.events, impacts, home, result.full_time_ms, lambda p: p or "?", lambda t: t or "?"
    )
    goals = [m for m in moments if m.kind == "goal"]
    assert len(goals) == 3
    by_id = {e.event_id: e for e in result.events}
    for goal in goals:
        assert [by_id[i].type for i in goal.evidence_event_ids] == ["shot", "goal"]
    assert [m.match_clock_ms for m in moments] == sorted(m.match_clock_ms for m in moments)


def test_team_stats_are_consistent() -> None:
    result, home = featured()
    impacts = event_impacts(result.events, home)
    at = 63 * 60_000
    home_stats = team_stats(result.events, impacts, home, home, at)
    away_stats = team_stats(result.events, impacts, result.away.club_id, home, at)
    assert (home_stats.goals, away_stats.goals) == result.score_at(at)
    assert abs(home_stats.possession_pct + away_stats.possession_pct - 100) < 0.2
    assert abs(home_stats.field_tilt_pct + away_stats.field_tilt_pct - 100) < 0.2
    assert home_stats.shots_on_target <= home_stats.shots
