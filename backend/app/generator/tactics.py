"""Tactical profiles: how each club plays.

The match engine follows these dials (where the back line holds, when to press, how wide to
play, how quickly and how directly to move the ball, whether to step up for offside), and the
knowledge corpus describes them in prose (`python -m app.generator.knowledge`). So when an agent
explains a match, it grounds its tactical claims in the same facts the match was played from.

Each club has a style, an archetype a coach would recognise, plus small deterministic variations,
so two possession sides play alike but not identically. Every dial runs from 0 to 1.
"""

import random
from dataclasses import dataclass, fields, replace
from typing import Literal

Style = Literal["possession", "high_press", "counter", "direct", "balanced"]


@dataclass(frozen=True)
class Tactics:
    style: Style
    line_height: float  # where the back line holds without the ball: 0 deep, 1 high
    press_height: float  # how far up the pitch they start closing down: 0 own third, 1 anywhere
    press_intensity: float  # how often the nearest player engages the ball carrier
    width: float  # how wide they spread with the ball: 0 narrow, 1 touchline to touchline
    compactness: float  # how tight the block gets without the ball: 0 loose, 1 very tight
    tempo: float  # how quickly the ball moves on: 0 patient, 1 quick
    directness: float  # preference for forward and longer passes over keeping the ball
    offside_trap: float  # how readily the back line steps up together to catch runners
    runs_in_behind: float  # how often forwards attack the space behind the defence


ARCHETYPES: dict[Style, Tactics] = {
    "possession": Tactics("possession", 0.70, 0.60, 0.55, 0.90, 0.60, 0.30, 0.20, 0.65, 0.40),
    "high_press": Tactics("high_press", 0.80, 0.90, 0.85, 0.75, 0.75, 0.70, 0.45, 0.75, 0.60),
    "counter": Tactics("counter", 0.25, 0.25, 0.40, 0.70, 0.90, 0.75, 0.75, 0.20, 0.85),
    "direct": Tactics("direct", 0.45, 0.45, 0.50, 0.80, 0.65, 0.65, 0.85, 0.35, 0.70),
    "balanced": Tactics("balanced", 0.50, 0.50, 0.55, 0.75, 0.70, 0.50, 0.50, 0.45, 0.55),
}

STYLE_NAMES: dict[Style, str] = {
    "possession": "possession",
    "high_press": "high press",
    "counter": "low block and counter",
    "direct": "direct",
    "balanced": "balanced",
}

STYLE_SUMMARIES: dict[Style, str] = {
    "possession": (
        "They build patiently from the back with short passes, spread wide to stretch the "
        "opposition, and push the defensive line high so the team stays compact around the ball. "
        "The high line squeezes the pitch, but it leaves space behind for quick forwards to attack."
    ),
    "high_press": (
        "They hunt the ball high up the pitch, with the nearest players closing down quickly and "
        "the rest pushing up behind them. Winning it back near the opponent's goal creates "
        "chances straight away. The cost is a high line and tired legs late in the game."
    ),
    "counter": (
        "They defend deep in a narrow, compact block, invite the opposition forward, and break "
        "quickly when they win the ball, looking for forwards running in behind. They give up "
        "possession and territory on purpose; their danger is the speed of the transition."
    ),
    "direct": (
        "They move the ball forward early, with longer passes into the forwards and runners "
        "attacking the space behind. They spend less time in midfield and accept losing the ball "
        "more often in exchange for getting it into dangerous areas quickly."
    ),
    "balanced": (
        "They mix short build-up with direct balls, press in midfield rather than high, and keep "
        "a medium defensive line. They adapt to the game rather than imposing one plan."
    ),
}

JITTER = 0.06  # how far each club's dials may differ from its archetype


def tactics_for(code: str, style: Style, seed: int) -> Tactics:
    """The club's profile: its archetype plus small variations fixed by the club and seed."""
    rng = random.Random(f"tactics/{seed}/{code}")  # str seeds are stable across runs
    base = ARCHETYPES[style]
    dials = {
        f.name: round(min(0.95, max(0.05, getattr(base, f.name) + rng.uniform(-JITTER, JITTER))), 2)
        for f in fields(Tactics)
        if f.name != "style"
    }
    return replace(base, **dials)


def describe(t: Tactics) -> list[tuple[str, str]]:
    """Each dial as a short phrase, for the knowledge corpus and the UI."""

    def level(value: float, low: str, mid: str, high: str) -> str:
        return low if value < 0.4 else high if value > 0.65 else mid

    return [
        ("Defensive line", level(t.line_height, "deep", "medium", "high")),
        ("Pressing starts", level(t.press_height, "in their own half", "in midfield", "high")),
        ("Pressing intensity", level(t.press_intensity, "selective", "steady", "relentless")),
        ("Width with the ball", level(t.width, "narrow", "moderate", "wide")),
        ("Shape without the ball", level(t.compactness, "stretched", "organised", "compact")),
        ("Tempo", level(t.tempo, "patient", "measured", "quick")),
        ("Passing", level(t.directness, "short and patient", "mixed", "direct")),
        ("Offside trap", level(t.offside_trap, "rarely", "sometimes", "often")),
        ("Runs in behind", level(t.runs_in_behind, "rare", "regular", "constant")),
    ]
