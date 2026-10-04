"""Proposal copy for the deterministic producer: one template per key-moment kind.

Every sentence states only what the cited events support (distance, xG, xT, speed, score), so the
rule "no claim without receipts" holds here as it will for the agents. Copy is written for both
audiences (analyst, casual) in English and Spanish; claims are the operator's receipts, in English.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from app.generator.world import Club
from app.models import Claim, MatchEvent
from app.models.insight import EventImpact, KeyMoment
from app.models.proposals import AudienceBody, LocalizedText, ProposalType
from app.state.xt import load_grid, to_frame


@dataclass(frozen=True)
class Copy:
    type: ProposalType
    headline: AudienceBody
    body: AudienceBody
    claims: list[Claim]
    player_id: str | None


@dataclass(frozen=True)
class CopyContext:
    events: dict[str, MatchEvent]
    impacts: dict[str, EventImpact]
    home_id: str
    surname: Callable[[str | None], str]
    club: Callable[[str | None], Club]
    score_at: Callable[[int], tuple[int, int]]


def audience(analyst: tuple[str, str], casual: tuple[str, str]) -> AudienceBody:
    return AudienceBody(
        analyst=LocalizedText(en=analyst[0], es=analyst[1]),
        casual=LocalizedText(en=casual[0], es=casual[1]),
    )


def es_number(value: float, digits: int) -> str:
    """A number in Spanish style: decimal comma."""
    return f"{value:.{digits}f}".replace(".", ",")


def distance_to_goal(e: MatchEvent, home: bool) -> int:
    assert e.location
    x, y = to_frame((e.location.x, e.location.y), home)
    return round(math.hypot((100 - x) * 1.05, (50 - y) * 0.68))


def minute_label(e: MatchEvent) -> str:
    return f"{e.minute + 1}'"


def moment_copy(moment: KeyMoment, ctx: CopyContext) -> Copy | None:
    """Proposal copy for a key moment, or None for kinds the producer does not propose."""
    evidence = [ctx.events[i] for i in moment.evidence_event_ids]
    lead = evidence[-1]
    builder = _BUILDERS.get(moment.kind)
    return builder(moment, evidence, lead, ctx) if builder else None


def _goal(
    moment: KeyMoment, evidence: list[MatchEvent], goal: MatchEvent, ctx: CopyContext
) -> Copy:
    shot = evidence[0]
    home = goal.team_id == ctx.home_id
    scorer, team = ctx.surname(goal.player_id), ctx.club(goal.team_id).name
    home_goals, away_goals = ctx.score_at(goal.match_clock_ms)
    ours, theirs = (home_goals, away_goals) if home else (away_goals, home_goals)
    xg = ctx.impacts[shot.event_id].threat
    dist = distance_to_goal(shot, home)
    if ours > theirs:
        state_en, state_es = f"{team} lead {ours}-{theirs}.", f"{team} gana {ours}-{theirs}."
    elif ours == theirs:
        state_en, state_es = f"It is level at {ours}-{theirs}.", f"Empate a {ours}."
    else:
        state_en, state_es = (
            f"{team} pull one back: {ours}-{theirs}.",
            f"{team} recorta distancias: {ours}-{theirs}.",
        )
    return Copy(
        type="narrative_line",
        headline=audience(
            (f"{scorer} scores for {team}", f"{scorer} marca para {team}"),
            (f"{scorer} scores!", f"¡Gol de {scorer}!"),
        ),
        body=audience(
            (
                f"{scorer} finishes from {dist} m, a chance worth {xg:.2f} xG. {state_en}",
                f"{scorer} define desde {dist} m, una ocasión de {es_number(xg, 2)} xG. {state_es}",
            ),
            (state_en, state_es),
        ),
        claims=[
            Claim(
                text=f"Goal by {scorer} at {minute_label(goal)}", evidence_event_ids=[goal.event_id]
            ),
            Claim(text=f"Shot from {dist} m worth {xg:.2f} xG", evidence_event_ids=[shot.event_id]),
        ],
        player_id=goal.player_id,
    )


_OUTCOME = {
    "saved": ("the keeper saves", "para el portero"),
    "off_target": ("it goes wide", "se va fuera"),
    "blocked": ("it is blocked", "lo bloquea la defensa"),
}


def _big_chance(
    moment: KeyMoment, evidence: list[MatchEvent], shot: MatchEvent, ctx: CopyContext
) -> Copy:
    home = shot.team_id == ctx.home_id
    shooter, team = ctx.surname(shot.player_id), ctx.club(shot.team_id).name
    xg = ctx.impacts[shot.event_id].threat
    dist = distance_to_goal(shot, home)
    outcome_en, outcome_es = _OUTCOME.get(shot.outcome or "", ("no goal", "no entra"))
    return Copy(
        type="narrative_line",
        headline=audience(
            (f"{shooter} goes close", f"{shooter} roza el gol"),
            (f"So close for {team}!", f"¡Qué cerca, {team}!"),
        ),
        body=audience(
            (
                f"A {xg:.2f} xG chance from {dist} m, but {outcome_en}.",
                f"Una ocasión de {es_number(xg, 2)} xG desde {dist} m, pero {outcome_es}.",
            ),
            (
                f"{shooter} had a great chance from {dist} m, but {outcome_en}.",
                f"{shooter} tuvo una gran ocasión desde {dist} m, pero {outcome_es}.",
            ),
        ),
        claims=[
            Claim(
                text=f"{shooter} shot from {dist} m worth {xg:.2f} xG ({outcome_en})",
                evidence_event_ids=[shot.event_id],
            )
        ],
        player_id=shot.player_id,
    )


def _save(
    moment: KeyMoment, evidence: list[MatchEvent], save: MatchEvent, ctx: CopyContext
) -> Copy:
    shot = evidence[0]
    keeper, shooter = ctx.surname(save.player_id), ctx.surname(shot.player_id)
    xg = ctx.impacts[shot.event_id].threat
    dist = distance_to_goal(shot, shot.team_id == ctx.home_id)
    return Copy(
        type="narrative_line",
        headline=audience(
            (f"{keeper} denies {shooter}", f"{keeper} le niega el gol a {shooter}"),
            (f"What a save from {keeper}!", f"¡Paradón de {keeper}!"),
        ),
        body=audience(
            (
                f"{keeper} stops a {xg:.2f} xG chance from {dist} m.",
                f"{keeper} detiene una ocasión de {es_number(xg, 2)} xG desde {dist} m.",
            ),
            (
                f"{shooter} was through from {dist} m and {keeper} kept it out.",
                f"{shooter} se plantó a {dist} m y {keeper} lo evitó.",
            ),
        ),
        claims=[
            Claim(
                text=f"{keeper} saved {shooter}'s {xg:.2f} xG shot",
                evidence_event_ids=[shot.event_id, save.event_id],
            )
        ],
        player_id=save.player_id,
    )


def _red_card(
    moment: KeyMoment, evidence: list[MatchEvent], card: MatchEvent, ctx: CopyContext
) -> Copy:
    player, team = ctx.surname(card.player_id), ctx.club(card.team_id).name
    return Copy(
        type="tactical_insight",
        headline=audience(
            (f"{team} down to ten men", f"{team} se queda con diez"),
            (f"Red card for {player}", f"Roja para {player}"),
        ),
        body=audience(
            (
                f"{player} is sent off at {minute_label(card)}; {team} play the rest with ten.",
                f"{player} es expulsado en el {minute_label(card)}; {team} jugará con diez.",
            ),
            (
                f"{player} is off, and {team} have to cope with ten.",
                f"{player} se va a la calle y {team} tendrá que aguantar con diez.",
            ),
        ),
        claims=[
            Claim(
                text=f"Red card for {player} at {minute_label(card)}",
                evidence_event_ids=[card.event_id],
            )
        ],
        player_id=card.player_id,
    )


def _decisive_pass(
    moment: KeyMoment, evidence: list[MatchEvent], pass_: MatchEvent, ctx: CopyContext
) -> Copy:
    passer, receiver = ctx.surname(pass_.player_id), ctx.surname(pass_.target_player_id)
    xt = ctx.impacts[pass_.event_id].threat
    assert pass_.end_location
    end = to_frame((pass_.end_location.x, pass_.end_location.y), pass_.team_id == ctx.home_id)
    chance = round(100 * load_grid().at(*end), 1)
    return Copy(
        type="stat_graphic",
        headline=audience(
            (f"{passer} opens them up", f"{passer} abre la defensa"),
            (f"Great ball from {passer}", f"Gran pase de {passer}"),
        ),
        body=audience(
            (
                f"The pass to {receiver} added {xt:.3f} xT: possession there leads to a goal "
                f"{chance}% of the time.",
                f"El pase a {receiver} sumó {es_number(xt, 3)} xT: desde ahí, la posesión acaba en "
                f"gol el {es_number(chance, 1)}% de las veces.",
            ),
            (
                f"{passer} found {receiver} in a really dangerous spot.",
                f"{passer} encontró a {receiver} en una zona muy peligrosa.",
            ),
        ),
        claims=[
            Claim(
                text=f"{passer} to {receiver} added {xt:.3f} xT",
                evidence_event_ids=[pass_.event_id],
            )
        ],
        player_id=pass_.player_id,
    )


def _ball_won(
    moment: KeyMoment, evidence: list[MatchEvent], tackle: MatchEvent, ctx: CopyContext
) -> Copy:
    player, team = ctx.surname(tackle.player_id), ctx.club(tackle.team_id).name
    dist = distance_to_goal(tackle, tackle.team_id == ctx.home_id)
    return Copy(
        type="tactical_insight",
        headline=audience(
            (f"{team} win it back high", f"{team} recupera arriba"),
            (f"{player} steals it", f"{player} roba el balón"),
        ),
        body=audience(
            (
                f"{player} wins the ball {dist} m from goal.",
                f"{player} recupera el balón a {dist} m de la portería.",
            ),
            (
                f"{player} pinches the ball right in the danger zone.",
                f"{player} roba el balón en plena zona de peligro.",
            ),
        ),
        claims=[
            Claim(
                text=f"{player} won the ball {dist} m from goal",
                evidence_event_ids=[tackle.event_id],
            )
        ],
        player_id=tackle.player_id,
    )


def _momentum_shift(
    moment: KeyMoment, evidence: list[MatchEvent], lead: MatchEvent, ctx: CopyContext
) -> Copy:
    team = ctx.club(moment.team_id).name
    threat = sum(ctx.impacts[e.event_id].threat for e in evidence)
    return Copy(
        type="tactical_insight",
        headline=audience(
            (f"{team} take control", f"{team} toma el control"),
            (f"{team} are on top now", f"{team} manda ahora"),
        ),
        body=audience(
            (
                f"Their last {len(evidence)} attacking actions added {threat:.2f} xT in three "
                "minutes.",
                f"Sus últimas {len(evidence)} acciones ofensivas sumaron "
                f"{es_number(threat, 2)} xT en tres minutos.",
            ),
            (
                f"{team} have pinned their opponents back.",
                f"{team} ha encerrado a su rival.",
            ),
        ),
        claims=[
            Claim(
                text=f"{len(evidence)} actions added {threat:.2f} xT in three minutes",
                evidence_event_ids=[e.event_id for e in evidence],
            )
        ],
        player_id=None,
    )


def sprint_copy(sprint: MatchEvent, fastest_so_far: bool, ctx: CopyContext) -> Copy:
    """A player tag for a high-speed run (the brief's threshold-triggered speed indicator)."""
    player = ctx.surname(sprint.player_id)
    speed = sprint.attributes.top_speed_kmh or 0
    meters = round(sprint.attributes.sprint_distance_m or 0)
    rank_en, rank_es = (
        ("the fastest of the match so far", "la más rápida del partido")
        if fastest_so_far
        else ("one of the quickest of the match", "una de las más rápidas del partido")
    )
    return Copy(
        type="player_tag",
        headline=audience(
            (f"{player} hits {speed:.1f} km/h", f"{player} alcanza {es_number(speed, 1)} km/h"),
            (f"{player} is flying", f"{player} vuela"),
        ),
        body=audience(
            (
                f"A {meters} m sprint at {speed:.1f} km/h, {rank_en}.",
                f"Un sprint de {meters} m a {es_number(speed, 1)} km/h, {rank_es}.",
            ),
            (
                f"{player} just hit {speed:.1f} km/h.",
                f"{player} acaba de alcanzar {es_number(speed, 1)} km/h.",
            ),
        ),
        claims=[
            Claim(
                text=f"Top speed {speed:.1f} km/h over {meters} m",
                evidence_event_ids=[sprint.event_id],
            )
        ],
        player_id=sprint.player_id,
    )


_BUILDERS = {
    "goal": _goal,
    "big_chance": _big_chance,
    "save": _save,
    "red_card": _red_card,
    "decisive_pass": _decisive_pass,
    "ball_won": _ball_won,
    "momentum_shift": _momentum_shift,
}
