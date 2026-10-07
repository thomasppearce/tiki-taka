"""Broadcast cues: what a producer covers between the defining plays.

Key moments (the aggregator's) are the plays that decide a match. Cues fill the broadcast around
them: an offside flag, a booking, a change, a stat check every ten minutes, a spell of territory,
the hardest runner. Each is built only from events, and every claim cites the events behind it,
the same rule the agents follow.
"""

from collections import defaultdict
from dataclasses import dataclass

from app.live.copy import Copy, CopyContext, audience, es_number, minute_label
from app.models import Claim, MatchEvent
from app.state.xt import to_frame

STATS_EVERY_MS = 10 * 60_000  # shots and xG at 10', 20', ...; territory five minutes later
TILT_WINDOW_MS = 10 * 60_000
TILT_SHARE = 0.65  # a side "pinning the other back": this share of final-third passes
TILT_MIN_PASSES = 8
FINAL_THIRD_X = 66.7
RUNNER_TAG_MINUTES = (30, 60, 85)
CLEAR_XG_GAP = 0.4  # below this, chances are "even"


@dataclass(frozen=True)
class Cue:
    at_ms: int  # when it can be proposed: all its evidence has happened by then
    key: str  # unique within the match; becomes the proposal's moment_id
    kind: str  # offside, booking, substitution, shots_xg, territory, runner
    label: str  # short English label for the audit log
    importance: float
    copy: Copy


def cues(
    events: list[MatchEvent], ctx: CopyContext, teams: tuple[str, str], full_time_ms: int
) -> list[Cue]:
    """Every cue in a match, in time order. `teams` is (home_id, away_id)."""
    out: list[Cue] = []
    offsides: dict[str, list[MatchEvent]] = defaultdict(list)
    for i, e in enumerate(events):
        if e.type == "offside" and e.team_id and i > 0:
            offsides[e.team_id].append(e)
            out.append(_offside(e, events[i - 1], list(offsides[e.team_id]), ctx, teams))
        elif e.type == "card" and e.attributes.card_color == "yellow":
            foul = next(
                (
                    x
                    for x in reversed(events[:i])
                    if x.type == "foul" and x.player_id == e.player_id
                ),
                None,
            )
            out.append(_booking(e, foul, ctx))
        elif e.type == "substitution" and e.target_player_id:
            out.append(_substitution(e, ctx))
    for t in range(STATS_EVERY_MS, full_time_ms, STATS_EVERY_MS):
        out += [c for c in (_shots_and_xg(events, t, ctx, teams),) if c]
        if t + STATS_EVERY_MS // 2 < full_time_ms:
            out += [c for c in (_territory(events, t + STATS_EVERY_MS // 2, ctx, teams),) if c]
    for minute in RUNNER_TAG_MINUTES:
        out += [c for c in (_hardest_runner(events, minute * 60_000, ctx),) if c]
    return sorted(out, key=lambda c: c.at_ms)


def _opponent(team_id: str | None, teams: tuple[str, str]) -> str:
    return teams[1] if team_id == teams[0] else teams[0]


def _offside(
    flag: MatchEvent,
    played: MatchEvent,
    team_flags: list[MatchEvent],
    ctx: CopyContext,
    teams: tuple[str, str],
) -> Cue:
    player, passer = ctx.surname(flag.player_id), ctx.surname(played.player_id)
    team = ctx.club(flag.team_id)
    opponent = ctx.club(_opponent(flag.team_id, teams))
    n = len(team_flags)
    claims = [
        Claim(
            text=f"{player} flagged offside at {minute_label(flag)} from {passer}'s pass",
            evidence_event_ids=[played.event_id, flag.event_id],
        )
    ]
    if n == 1:
        analyst = (
            f"{passer} looked for {player} in behind, but {player} was already past the "
            "last defender.",
            f"{passer} buscó a {player} a la espalda, pero {player} ya había rebasado al último "
            "defensor.",
        )
        casual = (f"{player} went too early.", f"{player} salió antes de tiempo.")
    else:
        claims.append(
            Claim(
                text=f"{team.name} have been caught offside {n} times",
                evidence_event_ids=[f.event_id for f in team_flags],
            )
        )
        analyst = (
            f"{team.name} caught offside {n} times now: {opponent.name}'s back line keeps "
            "catching their runs.",
            f"{team.name} ya suma {n} fueras de juego: la defensa del {opponent.name} sigue "
            "cazando sus desmarques.",
        )
        casual = (
            f"That's {n} offsides for {team.short}. The timing isn't there.",
            f"Ya van {n} fueras de juego para el {team.short}. No encuentran el momento.",
        )
    return Cue(
        at_ms=flag.match_clock_ms,
        key=f"cue_{flag.event_id[4:]}",
        kind="offside",
        label=f"Offside: {player} ({team.short} #{n})",
        importance=min(0.8, 0.6 + 0.06 * (n - 1)),
        copy=Copy(
            type="tactical_insight" if n > 1 else "narrative_line",
            headline=audience(
                (f"{player} caught offside", f"{player}, en fuera de juego"),
                (f"Flag up against {player}", f"Bandera arriba para {player}"),
            ),
            body=audience(analyst, casual),
            claims=claims,
            player_id=flag.player_id,
        ),
    )


def _booking(card: MatchEvent, foul: MatchEvent | None, ctx: CopyContext) -> Cue:
    player, team = ctx.surname(card.player_id), ctx.club(card.team_id)
    claims = [
        Claim(
            text=f"Yellow card for {player} at {minute_label(card)}",
            evidence_event_ids=[card.event_id],
        )
    ]
    if foul:
        claims.append(
            Claim(
                text=f"Booked for a foul at {minute_label(foul)}",
                evidence_event_ids=[foul.event_id],
            )
        )
    return Cue(
        at_ms=card.match_clock_ms,
        key=f"cue_{card.event_id[4:]}",
        kind="booking",
        label=f"Booked: {player}",
        importance=0.6,
        copy=Copy(
            type="narrative_line",
            headline=audience(
                (f"Yellow card: {player}", f"Tarjeta amarilla para {player}"),
                (f"{player} goes in the book", f"Amarilla para {player}"),
            ),
            body=audience(
                (
                    f"{player} ({team.short}) is booked at {minute_label(card)}. One more and "
                    f"{player} is off.",
                    f"{player} ({team.short}) ve la amarilla en el {minute_label(card)}. Otra más "
                    "y se va a la calle.",
                ),
                (
                    f"{player} will have to be careful now.",
                    f"{player} tendrá que tener cuidado ahora.",
                ),
            ),
            claims=claims,
            player_id=card.player_id,
        ),
    )


def _substitution(sub: MatchEvent, ctx: CopyContext) -> Cue:
    off, on = ctx.surname(sub.player_id), ctx.surname(sub.target_player_id)
    team = ctx.club(sub.team_id)
    km = (sub.attributes.distance_covered_m or 0) / 1000
    return Cue(
        at_ms=sub.match_clock_ms,
        key=f"cue_{sub.event_id[4:]}",
        kind="substitution",
        label=f"Change: {on} for {off}",
        importance=0.6,
        copy=Copy(
            type="narrative_line",
            headline=audience(
                (f"{team.short} change: {on} on for {off}", f"Cambio: entra {on} por {off}"),
                (f"{on} comes on", f"Entra {on}"),
            ),
            body=audience(
                (
                    f"{off} makes way after covering {km:.1f} km.",
                    f"{off} deja su sitio tras recorrer {es_number(km, 1)} km.",
                ),
                (
                    f"Fresh legs for {team.name}: {on} replaces {off}.",
                    f"Piernas frescas para el {team.name}: {on} sustituye a {off}.",
                ),
            ),
            claims=[
                Claim(
                    text=f"{on} replaced {off} at {minute_label(sub)}",
                    evidence_event_ids=[sub.event_id],
                ),
                Claim(text=f"{off} covered {km:.1f} km", evidence_event_ids=[sub.event_id]),
            ],
            player_id=sub.target_player_id,
        ),
    )


def _shots_and_xg(
    events: list[MatchEvent], t: int, ctx: CopyContext, teams: tuple[str, str]
) -> Cue | None:
    shots = [e for e in events if e.type == "shot" and e.match_clock_ms <= t]
    if len(shots) < 3:
        return None
    sides = [(ctx.club(tid), [s for s in shots if s.team_id == tid]) for tid in teams]
    xg = [sum(ctx.impacts[s.event_id].threat for s in team_shots) for _, team_shots in sides]
    (home, home_shots), (away, away_shots) = sides
    minute = t // 60_000
    lead = None if abs(xg[0] - xg[1]) < CLEAR_XG_GAP else (home if xg[0] > xg[1] else away)
    casual_head = (
        (f"{lead.name} creating more", f"{lead.name} genera más peligro")
        if lead
        else ("Chances even so far", "Igualdad en las ocasiones")
    )
    casual_body = (
        (
            f"{lead.name} have had the better chances after {minute} minutes.",
            f"{lead.name} ha tenido las mejores ocasiones tras {minute} minutos.",
        )
        if lead
        else (
            "Neither side has created much more than the other.",
            "Ninguno de los dos ha generado mucho más que el otro.",
        )
    )
    return Cue(
        at_ms=t,
        key=f"cue_stats_{minute}",
        kind="shots_xg",
        label=f"Shots and xG at {minute}'",
        importance=0.64,
        copy=Copy(
            type="stat_graphic",
            headline=audience(
                (
                    f"Shots {len(home_shots)}-{len(away_shots)}, xG {xg[0]:.1f}-{xg[1]:.1f}",
                    f"Tiros {len(home_shots)}-{len(away_shots)}, xG "
                    f"{es_number(xg[0], 1)}-{es_number(xg[1], 1)}",
                ),
                casual_head,
            ),
            body=audience(
                (
                    f"After {minute} minutes: {home.short} {len(home_shots)} shots worth "
                    f"{xg[0]:.2f} xG, {away.short} {len(away_shots)} worth {xg[1]:.2f}.",
                    f"Tras {minute} minutos: {home.short} {len(home_shots)} tiros por "
                    f"{es_number(xg[0], 2)} xG, {away.short} {len(away_shots)} por "
                    f"{es_number(xg[1], 2)}.",
                ),
                casual_body,
            ),
            claims=[
                Claim(
                    text=f"{club.name}: {len(team_shots)} shots worth {total:.2f} xG",
                    evidence_event_ids=[s.event_id for s in team_shots],
                )
                for (club, team_shots), total in zip(sides, xg, strict=True)
                if team_shots
            ],
            player_id=None,
        ),
    )


def _territory(
    events: list[MatchEvent], t: int, ctx: CopyContext, teams: tuple[str, str]
) -> Cue | None:
    home_id = teams[0]
    final_third: dict[str, list[MatchEvent]] = defaultdict(list)
    for e in events:
        if not t - TILT_WINDOW_MS < e.match_clock_ms <= t:
            continue
        if e.type == "pass" and e.outcome == "success" and e.end_location and e.team_id:
            x, _ = to_frame((e.end_location.x, e.end_location.y), e.team_id == home_id)
            if x > FINAL_THIRD_X:
                final_third[e.team_id].append(e)
    total = sum(len(p) for p in final_third.values())
    leader = max(teams, key=lambda tid: len(final_third[tid]))
    passes = final_third[leader]
    if len(passes) < TILT_MIN_PASSES or len(passes) < TILT_SHARE * total:
        return None
    team, opponent = ctx.club(leader), ctx.club(_opponent(leader, teams))
    share = round(100 * len(passes) / total)
    minute = t // 60_000
    return Cue(
        at_ms=t,
        key=f"cue_tilt_{minute}",
        kind="territory",
        label=f"Territory: {team.short} {share}%",
        importance=0.66,
        copy=Copy(
            type="tactical_insight",
            headline=audience(
                (
                    f"{team.name} pinning {opponent.short} back",
                    f"{team.name} encierra al {opponent.short}",
                ),
                (f"It's all {team.name}", f"Todo es del {team.name}"),
            ),
            body=audience(
                (
                    f"{share}% of completed final-third passes in the last ten minutes are "
                    f"{team.short}'s ({len(passes)} of {total}).",
                    f"El {share}% de los pases completados en el último tercio en los últimos "
                    f"diez minutos son del {team.short} ({len(passes)} de {total}).",
                ),
                (
                    f"{team.name} have camped in {opponent.name}'s half for ten minutes.",
                    f"{team.name} lleva diez minutos instalado en el campo del {opponent.name}.",
                ),
            ),
            claims=[
                Claim(
                    text=f"{len(passes)} of {total} completed final-third passes from "
                    f"{minute - 10}' to {minute}' were {team.short}'s",
                    evidence_event_ids=[p.event_id for p in passes],
                )
            ],
            player_id=None,
        ),
    )


def _hardest_runner(events: list[MatchEvent], t: int, ctx: CopyContext) -> Cue | None:
    latest: dict[str, MatchEvent] = {}
    for e in events:
        if e.match_clock_ms > t:
            break
        if e.player_id and e.attributes.distance_covered_m is not None:
            latest[e.player_id] = e
    if len(latest) < 2:
        return None
    ranked = sorted(latest.values(), key=lambda e: -(e.attributes.distance_covered_m or 0))
    best = ranked[0]
    player = ctx.surname(best.player_id)
    km = (best.attributes.distance_covered_m or 0) / 1000
    minute = t // 60_000
    return Cue(
        at_ms=t,
        key=f"cue_runner_{minute}",
        kind="runner",
        label=f"Hardest runner: {player} {km:.1f} km",
        importance=0.62,
        copy=Copy(
            type="player_tag",
            headline=audience(
                (f"{player}: {km:.1f} km covered", f"{player}: {es_number(km, 1)} km recorridos"),
                (f"{player} never stops", f"{player} no para"),
            ),
            body=audience(
                (
                    f"The most ground covered by anyone after {minute} minutes.",
                    f"Nadie ha recorrido más tras {minute} minutos.",
                ),
                (
                    f"{player} has run {km:.1f} km already, more than anyone else.",
                    f"{player} ya ha corrido {es_number(km, 1)} km, más que nadie.",
                ),
            ),
            claims=[
                Claim(
                    text=f"{player} had covered {km:.1f} km at {minute_label(best)}",
                    evidence_event_ids=[best.event_id],
                ),
                Claim(
                    text=f"More than any of the other {len(ranked) - 1} players so far",
                    evidence_event_ids=[e.event_id for e in ranked],
                ),
            ],
            player_id=best.player_id,
        ),
    )
