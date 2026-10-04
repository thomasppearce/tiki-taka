"""The match engine: deterministic, internally consistent, on-script, and realistic."""

from app.generator.engine import MatchEngine
from app.generator.matchday import FEATURED_MATCH_ID, build_matchday
from app.generator.storylines import STORYLINES
from app.generator.validation import validate
from app.generator.world import build_world


def test_world_is_deterministic_with_unique_players() -> None:
    world = build_world()
    assert world == build_world()
    player_ids = [p.player_id for league in world for club in league.clubs for p in club.squad]
    assert len(player_ids) == len(set(player_ids)) == 3 * 8 * 16


def test_same_seed_gives_the_same_match() -> None:
    home, away = build_world()[1].clubs[:2]
    story = STORYLINES["balanced"]
    first = MatchEngine("m_a", home, away, story, seed=11).run()
    second = MatchEngine("m_a", home, away, story, seed=11).run()
    assert first.events == second.events
    # Compare raw bytes: sent-off players are NaN in the frames, and NaN != NaN.
    assert first.frames.data.tobytes() == second.frames.data.tobytes()


def test_events_are_ordered_and_uniquely_identified() -> None:
    events = build_matchday()[0].result.events
    clocks = [e.match_clock_ms for e in events]
    assert clocks == sorted(clocks)
    assert len({e.event_id for e in events}) == len(events)


def test_the_ball_is_where_the_events_say() -> None:
    """Every pass starts where the tracking data has the ball at that instant."""
    result = build_matchday()[0].result
    passes = [e for e in result.events if e.type == "pass"]
    for e in passes[::25]:
        ball = result.frames.frame_at(e.match_clock_ms).ball
        assert e.location is not None
        assert abs(ball.x - e.location.x) < 3 and abs(ball.y - e.location.y) < 3, e.event_id


def test_frames_have_both_teams_on_the_pitch() -> None:
    result = build_matchday()[0].result
    frame = result.frames.frame_at(63 * 60_000)
    teams = {p.team_id for p in frame.players}
    assert teams == {result.home.club_id, result.away.club_id}
    assert 20 <= len(frame.players) <= 22
    assert all(-5 <= p.x <= 105 and -5 <= p.y <= 105 for p in frame.players)


def test_featured_match_follows_its_storyline() -> None:
    featured = next(m for m in build_matchday() if m.match_id == FEATURED_MATCH_ID)
    result = featured.result
    assert featured.featured and featured.storyline.name == "second_half_comeback"
    assert result.score_at(63 * 60_000) == (1, 0)
    assert result.score_at(result.full_time_ms) == (1, 2)


def test_demo_matchday_is_realistic() -> None:
    """At least 98% of realism checks pass, and any miss is a near miss, not a drift."""
    checks = [c for m in build_matchday() for c in validate(m.result)]
    failures = [c for c in checks if not c.ok]
    assert len(failures) <= len(checks) * 0.02, failures
    for c in failures:
        margin = 0.2 * (c.high - c.low)
        assert c.low - margin <= c.value <= c.high + margin, c
