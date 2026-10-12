"""The fictional football world: the Meridian League, its twenty clubs, and their squads.

Everything here is invented for this project: no real competitions, clubs, or players. Squads are
generated deterministically from name pools, except the featured fixture's two clubs, whose
players are written out because the demo and mock data refer to them by name.
"""

import random
from dataclasses import dataclass
from typing import Literal

from app.detmath import gauss
from app.generator.tactics import Style, Tactics, tactics_for

Role = Literal["gk", "def", "mid", "fwd"]


@dataclass(frozen=True)
class Player:
    player_id: str
    name: str
    number: int
    role: Role
    top_speed_mps: float  # 8.3-10.0 m/s is 30-36 km/h
    passing: float  # 0-1
    finishing: float  # 0-1
    work_rate: float  # 0-1, scales how hard they track and run


@dataclass(frozen=True)
class Club:
    club_id: str  # also the team_id used in events, e.g. "t_ngr"
    name: str
    short: str
    color: str  # brand color for crests and scorebug strips only (data views encode by role)
    formation: str  # a key of FORMATIONS
    squad: tuple[Player, ...]  # 11 starters in formation order, then 5 substitutes
    tactics: Tactics


@dataclass(frozen=True)
class League:
    league_id: str
    name: str
    clubs: tuple[Club, ...]


# Formation slots, in each team's own attacking frame (meters): x from own goal line (0) toward
# the opponent's (105), y across the pitch (0-68).
FORMATIONS: dict[str, tuple[tuple[Role, float, float], ...]] = {
    "4-4-2": (
        ("gk", 5, 34),
        ("def", 23, 58),
        ("def", 21, 42),
        ("def", 21, 26),
        ("def", 23, 10),
        ("mid", 46, 58),
        ("mid", 42, 41),
        ("mid", 42, 27),
        ("mid", 46, 10),
        ("fwd", 67, 39),
        ("fwd", 65, 28),
    ),
    "4-3-3": (
        ("gk", 5, 34),
        ("def", 25, 58),
        ("def", 23, 42),
        ("def", 23, 26),
        ("def", 25, 10),
        ("mid", 44, 34),
        ("mid", 48, 49),
        ("mid", 50, 20),
        ("fwd", 71, 57),
        ("fwd", 75, 34),
        ("fwd", 71, 11),
    ),
}

_SUB_ROLES: tuple[Role, ...] = ("gk", "def", "mid", "mid", "fwd")

_FIRST = [
    "Aarav",
    "Abel",
    "Adrian",
    "Alvaro",
    "Amadou",
    "Anders",
    "Aron",
    "Bastian",
    "Bram",
    "Caio",
    "Callum",
    "Casper",
    "Cian",
    "Dario",
    "Davi",
    "Declan",
    "Elias",
    "Emil",
    "Enzo",
    "Ezra",
    "Felix",
    "Finn",
    "Florian",
    "Gabriel",
    "Hamza",
    "Hugo",
    "Ilya",
    "Isak",
    "Ivo",
    "Jalen",
    "Jasper",
    "Joao",
    "Jonah",
    "Jonas",
    "Jules",
    "Kai",
    "Kenji",
    "Kofi",
    "Lasse",
    "Leon",
    "Levi",
    "Lior",
    "Luca",
    "Luka",
    "Malik",
    "Mateo",
    "Milo",
    "Musa",
    "Nils",
    "Noah",
    "Nolan",
    "Oisin",
    "Omar",
    "Oskar",
    "Pablo",
    "Rafa",
    "Rayan",
    "Remy",
    "Ruben",
    "Sami",
    "Santi",
    "Silas",
    "Soren",
    "Taro",
    "Teo",
    "Theo",
    "Tobias",
    "Tomas",
    "Viggo",
    "Wilf",
    "Yanis",
    "Yusuf",
    "Zane",
]
_LAST = [
    "Abara",
    "Achterberg",
    "Adeleke-Moss",
    "Aldana",
    "Ambrose",
    "Ancelin",
    "Arkwright",
    "Ashdown",
    "Baptiste",
    "Barraclough",
    "Bellamy",
    "Bergqvist",
    "Birchall",
    "Blackwood",
    "Bramwell",
    "Brannock",
    "Brodersen",
    "Calloway",
    "Carrow",
    "Castellan",
    "Chadwell",
    "Cheval",
    "Coldridge",
    "Corrigan",
    "Cosgrave",
    "Crabtree",
    "Dalgaard",
    "Danforth",
    "Delacroix",
    "Desrosiers",
    "Devereux",
    "Dornan",
    "Drummond-Ike",
    "Dunmore",
    "Eastwick",
    "Edevane",
    "Ekwueme",
    "Ellerby",
    "Esposti",
    "Falkenrath",
    "Farrant",
    "Faulkner",
    "Fenwick",
    "Fitzalan",
    "Fonseca-Lira",
    "Galloway",
    "Garrow",
    "Gerritsen",
    "Goldhawk",
    "Grimaldi-Shaw",
    "Hadley",
    "Halvorsen",
    "Harcourt",
    "Hardacre",
    "Heathcote",
    "Hollis",
    "Holmqvist",
    "Hunsdon",
    "Ibekwe",
    "Ingram",
    "Iwobi-Lane",
    "Jarrow",
    "Jervaise",
    "Jovanic",
    "Kallio",
    "Kemberton",
    "Kerrigan",
    "Kingsmill",
    "Kowalczyk-Reid",
    "Lachance",
    "Lambrecht",
    "Lindgren",
    "Lockhart",
    "Lomax",
    "Lucchesi",
    "Lyndhurst",
    "Madigan",
    "Marchetti",
    "Marwood",
    "Mbaye-Ross",
    "Merriman",
    "Mirabeau",
    "Montague",
    "Mortlake",
    "Moreau-Quist",
    "Nakamura-Hale",
    "Navarro-Pike",
    "Nettleford",
    "Northcott",
    "Nyborg",
    "Oakshott",
    "Odhiambo",
    "Okafor-Lind",
    "Oldroyd",
    "Orsini",
    "Ostergaard",
    "Palliser",
    "Pemberton",
    "Penhallow",
    "Pettersen",
    "Quarshie",
    "Quintero",
    "Rademaker",
    "Ravenhill",
    "Redfern",
    "Ridgeway",
    "Rosendahl",
    "Rowntree",
    "Rutherglen",
    "Salcedo",
    "Saltonstall",
    "Saunderson",
    "Scarrow",
    "Sedgwick",
    "Silvestri",
    "Solberg",
    "Southwold",
    "Stanbridge",
    "Strand-Holt",
    "Sverdrup",
    "Tavernier",
    "Tennant",
    "Thackeray",
    "Thornhill",
    "Toussaint",
    "Treloar",
    "Tregarthen",
    "Underhill",
    "Uzoma",
    "Valcourt",
    "Vanterpool",
    "Varga-Lind",
    "Vellacott",
    "Verhoeven-Dale",
    "Wakeling",
    "Warrender",
    "Westerholm",
    "Whitlock",
    "Wickham",
    "Wilberforce",
    "Winterbourne",
    "Wolfenden",
    "Wrexley",
    "Yardley",
    "Yeboah-Kent",
    "Ystad",
    "Zamorano",
    "Zeller",
    "Abernethy",
    "Albrecht-Owusu",
    "Ardagh",
    "Ballantyne",
    "Belcourt",
    "Borrowdale",
    "Brightwell",
    "Caddock",
    "Carmody",
    "Clemenceau",
    "Cotterell",
    "Dagenhart",
    "Delamere",
    "Dunleavy",
    "Etheridge",
    "Fairbairn",
    "Fennimore",
    "Glendinning",
    "Gravesend",
    "Haverford",
    "Hesketh",
    "Inchbald",
    "Kilbride",
    "Langstaff",
    "Larkhill",
    "Mallender",
    "Merrivale",
    "Oyelaran",
    "Ackroyd",
    "Adair",
    "Ainsworth",
    "Alderton",
    "Alvarenga",
    "Amsel",
    "Anand",
    "Antrobus",
    "Appiah",
    "Arkell",
    "Arnesen",
    "Ashby",
    "Aubin",
    "Ayodele",
    "Bakshi",
    "Banerjee",
    "Bascombe",
    "Beaumont",
    "Bellweather",
    "Benedetti",
    "Berrisford",
    "Bexley",
    "Birtwistle",
    "Bondarenko",
    "Bracewell",
    "Brannigan",
    "Brodsky",
    "Brunetti",
    "Buchholz",
    "Burkhart",
    "Cadogan",
    "Camborne",
    "Carraway",
    "Castellanos",
    "Chadwick",
    "Chaudhry",
    "Cheswick",
    "Cifuentes",
    "Claybourne",
    "Colquhoun",
    "Conroy",
    "Corcoran",
    "Cotterill",
    "Cruickshank",
    "Dalloway",
    "Danquah",
    "Darrow",
    "Demir",
    "Desmarais",
    "Dobrev",
    "Donnachie",
    "Drummond",
    "Dufresne",
    "Durrant",
    "Eastwood",
    "Echeverri",
    "Edgerton",
    "Ellery",
    "Embleton",
    "Engstrom",
    "Esposito",
    "Etherington",
    "Falconer",
    "Farquhar",
    "Ferrante",
    "Fleetwood",
    "Folau",
    "Fothergill",
    "Frampton",
    "Gallacher",
    "Garside",
    "Gathii",
    "Gilchrist",
    "Goldsworthy",
    "Gorecki",
    "Greenhalgh",
    "Grimshaw",
    "Gunnarsson",
    "Haddock",
    "Halloran",
    "Hirvonen",
    "Honeysett",
    "Horvath",
    "Huxley",
    "Ilunga",
    "Ingleby",
    "Iqbal",
    "Isherwood",
    "Jablonski",
    "Jardine",
    "Jessop",
    "Kaminski",
    "Kavanagh",
    "Kennaway",
    "Kingsley",
    "Kirkbride",
    "Kovalenko",
    "Lambourne",
    "Langridge",
    "Latimer",
    "Llewellyn",
    "Loughran",
    "Lowther",
    "Lyndon",
    "Macaulay",
    "Madsen",
    "Malmberg",
    "Manders",
    "Marchbank",
    "Merriweather",
    "Moorcroft",
    "Mortensen",
    "Mulvaney",
    "Nesbitt",
    "Nightingale",
    "Nwachukwu",
    "Oakes",
    "Ogilvy",
    "Orme",
    "Osterberg",
    "Otieno",
    "Overton",
    "Padgett",
    "Pardoe",
    "Pascoe",
    "Penhaligon",
    "Petrakis",
    "Prentice",
    "Pryce",
    "Quayle",
    "Radcliffe",
    "Rainford",
    "Rensburg",
    "Riordan",
    "Rockcliffe",
    "Rosales",
    "Rushworth",
    "Salazar",
    "Sandoval",
    "Scarisbrick",
    "Selwood",
    "Sherwin",
    "Sillitoe",
    "Skelton",
    "Soderberg",
    "Spellman",
    "Stanworth",
    "Strickland",
    "Sutcliffe",
    "Szabo",
    "Tamura",
    "Thistlewood",
    "Tolland",
    "Trelawney",
    "Tumelo",
    "Vasquez",
    "Verhoeven",
    "Waddington",
    "Wainwright",
    "Warburton",
    "Weatherall",
    "Winstanley",
    "Wolstenholme",
    "Woodburn",
    "Wyndham",
    "Zabala",
]

# The featured fixture's squads, written out (names the mock data and demo already use).
_FEATURED_SQUADS: dict[str, tuple[str, ...]] = {
    "ngr": (
        "Elias Varga",
        "Ruben Okoro-Lyle",
        "Callum Reyes-Booth",
        "Dario Pennant",
        "Sam Ferreira-Holt",
        "Lewis Achterberg",
        "Mateo Strand",
        "Rafa Quist",
        "Nico Varnaby",
        "Idris Kallo",
        "Theo Marlow",
        "Ben Arkwright",
        "Kasper Lomax",
        "Felix Garrow",
        "Omar Pemberton",
        "Leon Hollis",
    ),
    "wma": (
        "Anders Vik",
        "Tobias Wren",
        "Jonas Mbaye-Ross",
        "Callan Dumas-Reid",
        "Emil Gasparyan",
        "Ollie Kaczmarek",
        "Benedek Sato",
        "Yusuf Lindqvist",
        "Kofi Rasmussen",
        "Marco Desai",
        "Ilya Brannock",
        "Hugo Calloway",
        "Remy Dalgaard",
        "Silas Faulkner",
        "Teo Marchetti",
        "Zane Rowntree",
    ),
}
# Numbers by squad position, so the featured players keep their familiar shirt numbers.
_FEATURED_NUMBERS: dict[str, tuple[int, ...]] = {
    "ngr": (1, 2, 4, 5, 3, 7, 6, 8, 11, 9, 10, 13, 15, 16, 17, 19),
    "wma": (1, 2, 5, 4, 3, 6, 8, 10, 7, 9, 11, 13, 14, 16, 18, 20),
}

# (league name, [(club name, short code, brand color, formation)]): one league of twenty, listed
# in the order of the table going into the final day (app/generator/season.py).
_LEAGUES: tuple[tuple[str, tuple[tuple[str, str, str, str], ...]], ...] = (
    (
        "Meridian League",
        (
            ("Northgate Rovers", "NGR", "#2f6fd1", "4-4-2"),
            ("Halvern Town", "HVT", "#b8452f", "4-4-2"),
            ("Gullhaven FC", "GHV", "#1c5fa8", "4-3-3"),
            ("Tidewick Rovers", "TDR", "#d0662b", "4-4-2"),
            ("Kingsreach", "KRC", "#7a2c8f", "4-4-2"),
            ("Porthallow Athletic", "PHA", "#3a8f4a", "4-3-3"),
            ("Ironvale United", "IVU", "#9c2f2f", "4-4-2"),
            ("Mistral Bay", "MSB", "#2a9db0", "4-3-3"),
            ("Coldforge FC", "CFG", "#3e6f9e", "4-3-3"),
            ("Brackenford FC", "BRK", "#6b4fb8", "4-3-3"),
            ("Seacrest Town", "SCT", "#c9a227", "4-3-3"),
            ("Ashmoor Athletic", "ASM", "#6d5a3a", "4-4-2"),
            ("Redstack Rovers", "RSR", "#c0392b", "4-3-3"),
            ("Millbrook Town", "MBT", "#2f8a6b", "4-4-2"),
            ("Copperfield FC", "CPF", "#b5651d", "4-4-2"),
            ("Elmswick Rangers", "ELR", "#2c7f8f", "4-3-3"),
            ("Westmere Athletic", "WMA", "#1f9a6d", "4-3-3"),
            ("Corrin Bay", "CRB", "#c48a12", "4-3-3"),
            ("Dunhallow United", "DHU", "#8a1d3a", "4-4-2"),
            ("Lanterne Port FC", "LPT", "#b02a4a", "4-4-2"),
        ),
    ),
)


# The featured pair is a deliberate clash: Northgate's high possession line against Westmere's
# runners in behind. Every other club takes a style in rotation, so the league has a mix.
_STYLES: dict[str, Style] = {"ngr": "possession", "wma": "counter"}
_STYLE_ROTATION: tuple[Style, ...] = ("high_press", "direct", "balanced", "possession", "counter")


def build_world(seed: int = 2026) -> tuple[League, ...]:
    """The league with full squads. Same seed, same world."""
    rng = random.Random(seed)
    leagues = []
    for index, (league_name, clubs) in enumerate(_LEAGUES):
        built = []
        # Surnames are unique within a league, so labels like "Goal: Salcedo" are unambiguous.
        used: list[str] = [
            n.split(" ", 1)[1] for c in clubs for n in _FEATURED_SQUADS.get(c[1].lower(), ())
        ]
        for position, (name, short, color, formation) in enumerate(clubs):
            code = short.lower()
            style = _STYLES.get(code) or _STYLE_ROTATION[(position + index) % len(_STYLE_ROTATION)]
            built.append(
                Club(
                    club_id=f"t_{code}",
                    name=name,
                    short=short,
                    color=color,
                    formation=formation,
                    squad=_squad(code, formation, rng, used),
                    tactics=tactics_for(code, style, seed),
                )
            )
        leagues.append(League(league_id=f"l_{index + 1}", name=league_name, clubs=tuple(built)))
    return tuple(leagues)


def _squad(
    code: str, formation: str, rng: random.Random, used_surnames: list[str]
) -> tuple[Player, ...]:
    roles = [slot[0] for slot in FORMATIONS[formation]] + list(_SUB_ROLES)
    names = _FEATURED_SQUADS.get(code) or _unique_names(rng, len(roles), used_surnames)
    numbers = _FEATURED_NUMBERS.get(code) or _numbers(roles)
    return tuple(
        _player(code, name, number, role, rng)
        for name, number, role in zip(names, numbers, roles, strict=True)
    )


def _player(code: str, name: str, number: int, role: Role, rng: random.Random) -> Player:
    pace = {"gk": 8.0, "def": 8.9, "mid": 9.0, "fwd": 9.4}[role]
    return Player(
        player_id=f"p_{code}_{number:02d}",
        name=name,
        number=number,
        role=role,
        top_speed_mps=round(min(10.0, max(8.0, gauss(rng, pace, 0.35))), 2),
        passing=round(min(0.95, max(0.4, gauss(rng, 0.72 if role == "mid" else 0.64, 0.08))), 2),
        finishing=round(min(0.95, max(0.1, gauss(rng, 0.62 if role == "fwd" else 0.38, 0.1))), 2),
        work_rate=round(min(1.0, max(0.5, gauss(rng, 0.78, 0.1))), 2),
    )


def _unique_names(rng: random.Random, count: int, used_surnames: list[str]) -> list[str]:
    # Lists, not sets: set iteration order varies between runs and would break determinism.
    names: list[str] = []
    while len(names) < count:
        surname = rng.choice(_LAST)
        if surname in used_surnames:
            continue
        used_surnames.append(surname)
        names.append(f"{rng.choice(_FIRST)} {surname}")
    return names


def _numbers(roles: list[Role]) -> list[int]:
    starters = {"gk": [1], "def": [2, 5, 4, 3], "mid": [6, 8, 10, 7], "fwd": [9, 11, 7]}
    used: set[int] = set()
    numbers = []
    for i, role in enumerate(roles):
        pool = starters[role] if i < 11 else []
        n = next((x for x in pool if x not in used), None) or next(
            x for x in range(12, 40) if x not in used
        )
        used.add(n)
        numbers.append(n)
    return numbers
