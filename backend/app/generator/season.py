"""The season so far: the Meridian League table going into the final day.

Synthetic, and written to set up the final day's stories. The final day itself is played by the
engine (app/generator/matchday.py) and added to this table live (app/state/table.py):

- The title: Northgate lead Halvern by two points, with Halvern a goal better on goal difference.
  If Northgate fail to win and Halvern win, Halvern are champions.
- The drop: the bottom two are already down. Westmere and Corrin Bay, two points apart, fight
  over the last relegation place, and Corrin Bay are two goals better on goal difference.
- Fourth place: Tidewick, Kingsreach, and Porthallow are separated by two points.
"""

from dataclasses import dataclass
from typing import Literal

LEAGUE_GAMES = 38

Zone = Literal["champions", "continental", "relegation"]
# Positions (1-based, inclusive) of each zone in the twenty-club table.
ZONES: dict[Zone, tuple[int, int]] = {
    "champions": (1, 1),
    "continental": (2, 4),  # the continental cup places
    "relegation": (18, 20),
}


def zone_of(position: int) -> Zone | None:
    return next((z for z, (top, bottom) in ZONES.items() if top <= position <= bottom), None)


# (short, won, drawn, lost, goals for, goals against) after 37 games, in table order.
_TABLE: tuple[tuple[str, int, int, int, int, int], ...] = (
    ("NGR", 25, 7, 5, 78, 38),
    ("HVT", 24, 8, 5, 79, 38),
    ("GHV", 21, 8, 8, 66, 40),
    ("TDR", 19, 9, 9, 60, 44),
    ("KRC", 19, 8, 10, 58, 45),
    ("PHA", 18, 10, 9, 55, 42),
    ("IVU", 16, 10, 11, 54, 47),
    ("MSB", 15, 10, 12, 50, 46),
    ("CFG", 15, 8, 14, 49, 48),
    ("BRK", 14, 10, 13, 47, 47),
    ("SCT", 14, 8, 15, 46, 50),
    ("ASM", 13, 10, 14, 44, 49),
    ("RSR", 13, 8, 16, 45, 53),
    ("MBT", 12, 9, 16, 41, 52),
    ("CPF", 12, 8, 17, 42, 55),
    ("ELR", 11, 9, 17, 40, 56),
    ("WMA", 9, 10, 18, 38, 59),
    ("CRB", 9, 8, 20, 37, 56),
    ("DHU", 6, 10, 21, 31, 63),
    ("LPT", 5, 9, 23, 28, 70),
)


# The team of the season, picked before the final day: the fantasy XI a fan starts from (4-3-3,
# at most three from a club). Part of the story like the table above: the forwards who carried
# their clubs (Westmere's Desai and Sato in the drop fight), Halvern's title-race defence, and
# the keeper who kept Dunhallow in games all season.
TEAM_OF_THE_SEASON: tuple[str, ...] = (
    "p_dhu_01",
    "p_hvt_02",
    "p_hvt_05",
    "p_crb_04",
    "p_sct_02",
    "p_ivu_07",
    "p_wma_08",
    "p_asm_06",
    "p_wma_09",
    "p_elr_11",
    "p_lpt_09",
)


@dataclass(frozen=True)
class Record:
    club_id: str
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int

    @property
    def played(self) -> int:
        return self.won + self.drawn + self.lost

    @property
    def points(self) -> int:
        return 3 * self.won + self.drawn

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    def plus(self, scored: int, conceded: int) -> "Record":
        """This record with one more result added."""
        return Record(
            self.club_id,
            self.won + (scored > conceded),
            self.drawn + (scored == conceded),
            self.lost + (scored < conceded),
            self.goals_for + scored,
            self.goals_against + conceded,
        )


def table_before_final_day() -> tuple[Record, ...]:
    """Every club's record after 37 games. Club ids are the world's (t_ngr, ...)."""
    return tuple(Record(f"t_{short.lower()}", *rest) for short, *rest in _TABLE)
