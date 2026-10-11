"""The match engine: deterministic, internally consistent, on-script, and realistic."""

import math
import statistics

from app.generator.engine import MatchEngine
from app.generator.matchday import FEATURED_MATCH_ID, build_matchday
from app.generator.storylines import STORYLINES
from app.generator.tactics import tactics_for
from app.generator.validation import clear_sight_shot_share, validate
from app.generator.world import build_world


def test_world_is_deterministic_with_unique_players() -> None:
    world = build_world()
    assert world == build_world()
    player_ids = [p.player_id for league in world for club in league.clubs for p in club.squad]
    assert len(player_ids) == len(set(player_ids)) == 20 * 16
    surnames = [p.name.split(" ", 1)[1] for league in world for c in league.clubs for p in c.squad]
    assert len(set(surnames)) == len(surnames)  # so "Goal: Marlow" is never ambiguous


def test_same_seed_gives_the_same_match() -> None:
    home, away = build_world()[0].clubs[2:4]
    story = STORYLINES["balanced"]
    first = MatchEngine("m_a", home, away, story, seed=11).run()
    second = MatchEngine("m_a", home, away, story, seed=11).run()
    assert first.events == second.events
    # Compare raw bytes: sent-off players are NaN in the frames, and NaN != NaN.
    assert first.frames.data.tobytes() == second.frames.data.tobytes()


def test_the_final_day_goals_land_in_story_order() -> None:
    """The title and the last relegation place are written around five goals in three matches
    (app/generator/season.py); they must come in this order for the stories to work."""
    matches = {(m.home.short, m.away.short): m for m in build_matchday()}

    def goals(home: str, away: str) -> list[tuple[int, str]]:
        m = matches[(home, away)]
        return [
            (e.match_clock_ms, m.home.short if e.team_id == m.home.club_id else m.away.short)
            for e in m.result.events
            if e.type == "goal"
        ]

    featured, halvern, corrin = goals("NGR", "WMA"), goals("BRK", "HVT"), goals("CRB", "MBT")
    assert [side for _, side in featured] == ["NGR", "WMA", "WMA"]
    assert [side for _, side in halvern] == ["HVT"] and [side for _, side in corrin] == ["CRB"]
    order = [featured[0][0], corrin[0][0], featured[1][0], halvern[0][0], featured[2][0]]
    assert order == sorted(order)  # NGR lead, CRB lead, WMA level, HVT lead, WMA winner


def test_events_are_ordered_and_uniquely_identified() -> None:
    events = build_matchday()[0].result.events
    clocks = [e.match_clock_ms for e in events]
    assert clocks == sorted(clocks)
    assert len({e.event_id for e in events}) == len(events)


def test_the_ball_is_where_the_events_say() -> None:
    """Every pass starts where the tracking data has the ball at that instant. Frames are
    recorded every 0.4 s and events every 0.2 s, so allow half a frame of ball travel."""
    result = build_matchday()[0].result
    passes = [e for e in result.events if e.type == "pass"]
    for e in passes[::25]:
        ball = result.frames.frame_at(e.match_clock_ms).ball
        assert e.location is not None
        gap_m = math.hypot((ball.x - e.location.x) * 1.05, (ball.y - e.location.y) * 0.68)
        assert gap_m < 4.0, e.event_id


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


def test_nobody_teleports() -> None:
    """Between consecutive frames, across the whole matchday, no player moves faster than a
    sprinter and the ball no faster than a shot: play flows continuously through restarts,
    goals, and half-time, with nobody placed directly."""
    for m in build_matchday():
        frames = m.result.frames
        d, stride = frames.data, frames.STRIDE
        seconds = frames.FRAME_MS / 1000
        for k in range(1, frames.count):
            a, b = (k - 1) * stride, k * stride
            ball = math.hypot(d[b] - d[a], d[b + 1] - d[a + 1])
            assert ball <= 36 * seconds, (m.match_id, k * frames.FRAME_MS, "ball", ball)
            for i in range(2, stride, 2):
                if math.isnan(d[a + i]) or math.isnan(d[b + i]):
                    continue  # sent off
                step = math.hypot(d[b + i] - d[a + i], d[b + i + 1] - d[a + i + 1])
                assert step <= 10.5 * seconds, (m.match_id, k * frames.FRAME_MS, i // 2 - 1, step)


def test_offside_is_called_on_the_pass_and_the_defenders_restart() -> None:
    offsides = 0
    for m in build_matchday():
        events = m.result.events
        for i, e in enumerate(events):
            if e.type != "offside":
                continue
            offsides += 1
            played = events[i - 1]
            assert played.type == "pass" and played.outcome == "fail"
            assert (played.team_id, played.target_player_id) == (e.team_id, e.player_id)
            restart = next((x for x in events[i + 1 :] if x.type in ("pass", "shot")), None)
            assert restart is None or restart.team_id != e.team_id  # None: flagged at the whistle
    assert offsides > 0


def test_tactics_change_how_teams_defend() -> None:
    """Sides told to hold a high line keep their back four well above deep-block sides."""
    high, deep = [], []
    for m in build_matchday():
        frames = m.result.frames
        for club, first_slot, home in ((m.home, 1, True), (m.away, 12, False)):
            xs = [
                frames.data[k * frames.STRIDE + 2 + slot * 2]
                for k in range(0, frames.count, 10)
                for slot in range(first_slot, first_slot + 4)
            ]
            height = statistics.mean(x if home else 105 - x for x in xs if not math.isnan(x))
            if club.tactics.line_height >= 0.65:
                high.append(height)
            elif club.tactics.line_height <= 0.35:
                deep.append(height)
    assert high and deep
    assert statistics.mean(high) > statistics.mean(deep) + 4


def test_tactics_are_deterministic_and_varied() -> None:
    assert tactics_for("ngr", "possession", 2026) == tactics_for("ngr", "possession", 2026)
    assert tactics_for("ngr", "possession", 2026) != tactics_for("brk", "possession", 2026)
    for league in build_world():
        assert len({club.tactics.style for club in league.clubs}) >= 4


def test_the_scripted_goals_have_their_scorers_and_the_winner_comes_at_the_death() -> None:
    """The story names its scorers (they are kept on the pitch until they score) and the
    title and the drop are settled in stoppage time."""
    matches = {m.match_id: m for m in build_matchday()}

    def scorers(match_id: str) -> list[str]:
        m = matches[match_id]
        names = {p.player_id: p.name.split()[-1] for c in (m.home, m.away) for p in c.squad}
        return [names[e.player_id or ""] for e in m.result.events if e.type == "goal"]

    assert scorers(FEATURED_MATCH_ID) == ["Marlow", "Desai", "Desai"]
    assert scorers("m_l1_2") == ["Ambrose"] and scorers("m_l1_3") == ["Radcliffe"]
    winner = [e for e in matches[FEATURED_MATCH_ID].result.events if e.type == "goal"][-1]
    assert winner.match_clock_ms > 90 * 60_000


def test_forwards_shoot_when_through_on_goal() -> None:
    """Through on goal with only the keeper to beat, most players shoot (a viewer once saw
    them pass it up); across the day, at least two in three do."""
    shares = [clear_sight_shot_share(m.result) for m in build_matchday()]
    assert statistics.mean(shares) >= 0.6, shares


def test_restarts_are_taken_without_being_challenged() -> None:
    """Opponents stand back at free kicks and corners, and nobody challenges a restart before
    it is played: every restart's next action is the restarting side's pass or shot."""
    for m in build_matchday():
        events = m.result.events
        for i, e in enumerate(events):
            if e.type not in ("free_kick", "corner", "throw_in", "goal_kick"):
                continue
            nxt = next(
                (
                    x
                    for x in events[i + 1 :]
                    if x.type in ("pass", "shot", "foul", "tackle", "half_end", "goal")
                ),
                None,
            )
            if nxt is not None and nxt.type in ("half_end", "goal"):
                continue  # the half ended before it was taken
            if nxt is not None and nxt.type not in ("pass", "shot"):
                raise AssertionError(f"{m.match_id}: {nxt.type} before {e.type} {e.event_id}")
            assert nxt is None or nxt.team_id == e.team_id, (m.match_id, e.event_id)
            if e.type in ("free_kick", "corner") and nxt:
                # Just before it is taken (the taker plays it within a second of taking it);
                # once it's taken they may close in.
                frame = m.result.frames.frame_at(nxt.match_clock_ms - 1_500)
                ball = (frame.ball.x / 100 * 105, frame.ball.y / 100 * 68)
                for p in frame.players:
                    if p.team_id != e.team_id:
                        gap = math.hypot(p.x / 100 * 105 - ball[0], p.y / 100 * 68 - ball[1])
                        # They walk back toward 9.15 m: near the mark, never over the ball.
                        assert gap > 7, (m.match_id, e.event_id, p.player_id, gap)


def test_a_foul_in_the_box_is_a_penalty() -> None:
    """No free kick is ever given inside the box it's taken toward: a foul there is a penalty,
    taken from the spot with everyone else outside the area. Matches whose goals are all
    written by the story have none (defenders there never risk one)."""
    penalties = 0
    for m in build_matchday():
        events = m.result.events
        for i, e in enumerate(events):
            if e.type not in ("free_kick", "penalty") or not e.location:
                continue
            home = e.team_id == m.home.club_id
            x, y = e.location.x / 100 * 105, e.location.y / 100 * 68
            to_goal = 105 - x if home else x
            in_box = to_goal < 16.5 and abs(y - 34) < 20.16
            if e.type == "free_kick":
                assert not in_box, (m.match_id, e.event_id)
                continue
            penalties += 1
            assert m.storyline.finishing != (0.0, 0.0), m.match_id
            kick = next(x for x in events[i + 1 :] if x.type == "shot")
            assert kick.player_id == e.player_id  # the taker named takes it
            frame = m.result.frames.frame_at(kick.match_clock_ms)
            keeper = next(c for c in (m.home, m.away) if c.club_id != e.team_id).squad[0]
            for p in frame.players:
                if p.player_id in (e.player_id, keeper.player_id):
                    continue
                px, py = p.x / 100 * 105, p.y / 100 * 68
                depth = 105 - px if home else px
                assert not (depth < 15.5 and abs(py - 34) < 19), (m.match_id, p.player_id)
    assert penalties > 0
