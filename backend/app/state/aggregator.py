"""The aggregator: turns raw match events into importance, momentum, key moments, and stats.

Everything here is deterministic and explainable. Importance comes from the expected-threat grid
(app.state.xt) and a location xG model, so every number can be traced back to the events it was
computed from: the Explainer can cite them, and the UI can show only the plays that matter.
"""

import math
from collections.abc import Callable, Sequence

from app.detmath import atan2
from app.generator.engine import expected_goals
from app.models import MatchEvent
from app.models.insight import EventImpact, KeyMoment, TeamStats
from app.state.xt import XTGrid, load_grid, to_frame

# Scales that map raw swings to a 0-1 importance.
PASS_THREAT_SCALE = 0.05  # xT added by a pass that counts as a decisive pass
TACKLE_SWING_SCALE = 0.04  # xT swing of a tackle that wins the ball back somewhere dangerous
BIG_CHANCE_XG = 0.15
HIGH_REGAIN_X = 60  # "won it back high": a tackle this far up the pitch (attacking frame)
REGAIN_GAP_MS = 120_000  # one high regain per player per two minutes
MOMENTUM_DECAY = 0.7  # per minute, ~2 minute half-life
MOMENTUM_FLOOR = 0.02  # keeps quiet spells near zero instead of swinging wildly

PlayerName = Callable[[str | None], str]


def _xg(e: MatchEvent, home: bool) -> float:
    assert e.location
    x, y = to_frame((e.location.x, e.location.y), home)
    mx, my = x * 1.05, y * 0.68
    return expected_goals(math.hypot(105 - mx, 34 - my), abs(atan2(my - 34, 105 - mx)))


def event_impacts(
    events: Sequence[MatchEvent], home_id: str, grid: XTGrid | None = None
) -> dict[str, EventImpact]:
    """Threat added and importance for every event."""
    grid = grid or load_grid()
    impacts: dict[str, EventImpact] = {}
    last_shot: EventImpact | None = None
    for e in events:
        threat, importance = 0.0, 0.0
        home = e.team_id == home_id
        if e.location and e.team_id:
            start = grid.at(*to_frame((e.location.x, e.location.y), home))
            if e.type == "pass":
                if e.outcome == "success" and e.end_location:
                    end = grid.at(*to_frame((e.end_location.x, e.end_location.y), home))
                    threat = end - start
                    # Forward progress matters; a safe pass backwards is just recycling.
                    weight = 1.0 if threat > 0 else 0.15
                else:
                    threat = -start  # possession lost: the threat the team had is gone
                    weight = 0.8
                importance = min(1.0, weight * abs(threat) / PASS_THREAT_SCALE)
            elif e.type == "shot":
                threat = _xg(e, home)
                importance = min(0.9, 0.3 + threat * 1.5)  # below a goal, however good the chance
            elif e.type == "goal":
                importance = 1.0
            elif e.type == "tackle":
                # Winning the ball is worth what the tackler's side gains plus what the other loses.
                lost = grid.at(*to_frame((e.location.x, e.location.y), not home))
                threat = start
                importance = min(1.0, (start + lost) / TACKLE_SWING_SCALE)
            elif e.type == "save" and last_shot:
                importance = 0.9 * last_shot.importance
            elif e.type == "card":
                importance = 0.7 if e.attributes.card_color == "red" else 0.2
            elif e.type == "foul":
                victim_side = grid.at(*to_frame((e.location.x, e.location.y), not home))
                importance = min(1.0, victim_side / PASS_THREAT_SCALE)
            elif e.type == "pressure":
                importance = 0.1 * (e.attributes.pressure_level or 0)
            elif e.type == "sprint":
                importance = 0.05 + max(0.0, (e.attributes.top_speed_kmh or 0) - 30) / 25
            elif e.type == "substitution":
                importance = 0.05
        impact = EventImpact(
            event_id=e.event_id,
            team_id=e.team_id,
            threat=round(threat, 4),
            importance=round(min(1.0, max(0.0, importance)), 3),
        )
        if e.type == "shot":
            last_shot = impact
        impacts[e.event_id] = impact
    return impacts


def momentum(
    events: Sequence[MatchEvent],
    impacts: dict[str, EventImpact],
    home_id: str,
    until_ms: float,
) -> list[float]:
    """Per minute, -1 (away on top) to 1 (home on top): each side's share of recent threat.

    Threat created (completed passes that move the ball forward, plus shot xG) is summed per
    minute and smoothed with an exponential decay, then compared between the sides.
    """
    minutes = int(until_ms // 60_000) + 1
    gains = {True: [0.0] * minutes, False: [0.0] * minutes}
    for e in events:
        if e.match_clock_ms > until_ms or not e.team_id:
            continue
        threat = impacts[e.event_id].threat
        if threat > 0 and e.type in ("pass", "shot"):
            gains[e.team_id == home_id][e.match_clock_ms // 60_000] += threat
    series = []
    home_rate = away_rate = 0.0
    for m in range(minutes):
        home_rate = home_rate * MOMENTUM_DECAY + gains[True][m]
        away_rate = away_rate * MOMENTUM_DECAY + gains[False][m]
        series.append(round((home_rate - away_rate) / (home_rate + away_rate + MOMENTUM_FLOOR), 3))
    return series


def key_moments(
    events: Sequence[MatchEvent],
    impacts: dict[str, EventImpact],
    home_id: str,
    until_ms: float,
    name: PlayerName,
    team_short: Callable[[str | None], str],
) -> list[KeyMoment]:
    """The defining plays so far, oldest first."""
    seen = [e for e in events if e.match_clock_ms <= until_ms]
    moments: list[KeyMoment] = []

    def add(kind: str, e: MatchEvent, label: str, importance: float, evidence: list[str]) -> None:
        moments.append(
            KeyMoment(
                moment_id=f"km_{e.event_id[4:]}",
                kind=kind,  # type: ignore[arg-type]
                match_clock_ms=e.match_clock_ms,
                team_id=e.team_id,
                label=label,
                importance=round(min(1.0, importance), 3),
                evidence_event_ids=evidence,
            )
        )

    previous_shot: MatchEvent | None = None
    last_regain: dict[str | None, int] = {}
    for e in seen:
        impact = impacts[e.event_id]
        if e.type == "goal":
            evidence = [previous_shot.event_id, e.event_id] if previous_shot else [e.event_id]
            add("goal", e, f"Goal: {name(e.player_id)}", 1.0, evidence)
        elif e.type == "shot":
            previous_shot = e
            if e.outcome != "goal" and impact.threat >= BIG_CHANCE_XG:
                add(
                    "big_chance",
                    e,
                    f"Big chance: {name(e.player_id)} (xG {impact.threat:.2f})",
                    impact.importance,
                    [e.event_id],
                )
        elif e.type == "save" and previous_shot and impacts[previous_shot.event_id].threat >= 0.1:
            add(
                "save",
                e,
                f"Save: {name(e.player_id)} denies {name(previous_shot.player_id)}",
                impact.importance,
                [previous_shot.event_id, e.event_id],
            )
        elif e.type == "card" and e.attributes.card_color == "red":
            add("red_card", e, f"Red card: {name(e.player_id)}", impact.importance, [e.event_id])
        elif e.type == "pass" and impact.threat > 0 and impact.importance >= 0.85:
            target = name(e.target_player_id)
            add(
                "decisive_pass",
                e,
                f"{name(e.player_id)} finds {target} (+{impact.threat:.3f} xT)",
                impact.importance * 0.8,
                [e.event_id],
            )
        elif (
            e.type == "tackle"
            and impact.importance >= 0.85
            and e.location is not None
            and to_frame((e.location.x, e.location.y), e.team_id == home_id)[0] >= HIGH_REGAIN_X
            and e.match_clock_ms - last_regain.get(e.player_id, -REGAIN_GAP_MS) >= REGAIN_GAP_MS
        ):
            last_regain[e.player_id] = e.match_clock_ms
            add(
                "ball_won",
                e,
                f"{name(e.player_id)} wins it back high",
                impact.importance * 0.6,
                [e.event_id],
            )

    # Momentum shifts: the curve swings to one side and stays there for three minutes.
    curve = momentum(events, impacts, home_id, until_ms)
    last_shift = {True: -10, False: -10}
    for m in range(3, len(curve) - 2):
        for home_side in (True, False):
            sign = 1 if home_side else -1
            if m - last_shift[home_side] < 6:
                continue
            if not (sign * curve[m - 3] < 0.1 and all(sign * v > 0.45 for v in curve[m : m + 3])):
                continue
            drivers = sorted(
                (
                    e
                    for e in seen
                    if m * 60_000 <= e.match_clock_ms < (m + 3) * 60_000
                    and (e.team_id == home_id) == home_side
                    and impacts[e.event_id].threat > 0
                ),
                key=lambda e: -impacts[e.event_id].threat,
            )[:4]
            if not drivers:
                continue
            last_shift[home_side] = m
            moments.append(
                KeyMoment(
                    moment_id=f"km_shift_{m}",
                    kind="momentum_shift",
                    match_clock_ms=m * 60_000,
                    team_id=drivers[0].team_id,
                    label=f"{team_short(drivers[0].team_id)} take control",
                    importance=0.6,
                    evidence_event_ids=[
                        e.event_id for e in sorted(drivers, key=lambda e: e.match_clock_ms)
                    ],
                )
            )
    return sorted(moments, key=lambda k: k.match_clock_ms)


def team_stats(
    events: Sequence[MatchEvent],
    impacts: dict[str, EventImpact],
    team_id: str,
    home_id: str,
    until_ms: float,
) -> TeamStats:
    seen = [e for e in events if e.match_clock_ms <= until_ms and e.team_id]
    mine = [e for e in seen if e.team_id == team_id]
    passes = [e for e in mine if e.type == "pass"]
    all_passes = sum(1 for e in seen if e.type == "pass")
    shots = [e for e in mine if e.type == "shot"]

    def final_third(e: MatchEvent) -> bool:
        if e.type != "pass" or not e.end_location:
            return False
        x, _ = to_frame((e.end_location.x, e.end_location.y), e.team_id == home_id)
        return x > 66.7

    mine_ft = sum(1 for e in passes if final_third(e))
    all_ft = sum(1 for e in seen if final_third(e))
    return TeamStats(
        team_id=team_id,
        goals=sum(1 for e in mine if e.type == "goal"),
        shots=len(shots),
        shots_on_target=sum(1 for e in shots if e.outcome in ("saved", "goal")),
        xg=round(sum(impacts[e.event_id].threat for e in shots), 2),
        passes=len(passes),
        pass_accuracy=round(sum(e.outcome == "success" for e in passes) / max(1, len(passes)), 3),
        possession_pct=round(100 * len(passes) / max(1, all_passes), 1),
        field_tilt_pct=round(100 * mine_ft / max(1, all_ft), 1),
        tackles=sum(1 for e in mine if e.type == "tackle"),
        fouls=sum(1 for e in mine if e.type == "foul"),
        offsides=sum(1 for e in mine if e.type == "offside"),
        yellow_cards=sum(
            1 for e in mine if e.type == "card" and e.attributes.card_color == "yellow"
        ),
        red_cards=sum(1 for e in mine if e.type == "card" and e.attributes.card_color == "red"),
    )
