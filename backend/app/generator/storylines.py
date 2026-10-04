"""Scripted storylines: how a match should feel, and the beats it must hit.

A storyline has a dominance curve (who is on top, minute by minute) that tilts the engine's
probabilities, plus beats: goals and red cards that must happen near given minutes. Beats are
what guarantee a demo match has its story; dominance makes the play around them look earned.
"""

from dataclasses import dataclass
from typing import Literal

Side = Literal["home", "away"]


@dataclass(frozen=True)
class Beat:
    minute: float
    kind: Literal["goal", "red_card"]
    side: Side
    player_number: int | None = None  # preferred scorer; ignored if not on the pitch


@dataclass(frozen=True)
class Storyline:
    name: str
    description: str
    # (minute, dominance) points; dominance in [-1, 1], positive favors the home side.
    dominance: tuple[tuple[float, float], ...]
    beats: tuple[Beat, ...] = ()
    # Shot conversion multipliers (home, away) outside the beats.
    finishing: tuple[float, float] = (1.0, 1.0)

    def dominance_at(self, minute: float) -> float:
        points = self.dominance
        if minute <= points[0][0]:
            return points[0][1]
        for (m0, d0), (m1, d1) in zip(points, points[1:], strict=False):
            if m0 <= minute <= m1:
                return d0 + (d1 - d0) * (minute - m0) / (m1 - m0)
        return points[-1][1]


STORYLINES: dict[str, Storyline] = {
    s.name: s
    for s in (
        Storyline(
            "balanced",
            "An even contest; whatever happens, happens.",
            ((0, 0.0), (95, 0.0)),
        ),
        Storyline(
            "second_half_comeback",
            "Home take an early lead; away dominate after the break and turn it around late.",
            ((0, 0.25), (40, 0.25), (52, 0.0), (58, -0.55), (95, -0.6)),
            (
                Beat(23, "goal", "home", 9),
                Beat(71, "goal", "away", 9),
                Beat(86, "goal", "away", 10),
            ),
            # The featured demo match: only the scripted goals, so it tells exactly this story.
            finishing=(0.0, 0.0),
        ),
        Storyline(
            "late_collapse",
            "Home cruise to a two-goal lead, then fall apart in the last quarter of an hour.",
            ((0, 0.4), (68, 0.35), (76, -0.5), (95, -0.7)),
            (
                Beat(18, "goal", "home"),
                Beat(52, "goal", "home"),
                Beat(78, "goal", "away"),
                Beat(84, "goal", "away"),
                Beat(90, "goal", "away"),
            ),
            finishing=(0.35, 0.35),  # five scripted goals already
        ),
        Storyline(
            "red_card_swing",
            "A first-half red card for the home side swings the match.",
            ((0, 0.1), (34, 0.1), (36, -0.4), (95, -0.4)),
            (Beat(34, "red_card", "home"), Beat(61, "goal", "away")),
            finishing=(0.7, 0.7),  # ten men concede chances; keep the scoreline believable
        ),
        Storyline(
            "dominant_but_wasteful",
            "Home have all the ball and all the chances, and lose to one counter.",
            ((0, 0.55), (95, 0.55)),
            (Beat(74, "goal", "away"),),
            finishing=(0.25, 1.0),
        ),
        Storyline(
            "end_to_end",
            "Both sides attack; goals at both ends.",
            ((0, 0.15), (30, -0.15), (60, 0.15), (95, -0.1)),
            (
                Beat(12, "goal", "home"),
                Beat(27, "goal", "away"),
                Beat(66, "goal", "home"),
                Beat(88, "goal", "away"),
            ),
            finishing=(0.6, 0.6),  # four scripted goals already
        ),
    )
}
