# Synthetic match data

Match Desk runs on football-realistic data it generates itself: no real match data, clubs, or players. This page explains how the generator works and how its realism is checked.

## The world

`backend/app/generator/world.py` builds three fictional leagues (Meridian League, Harbour Coast League, Ironvale League) of 8 clubs each, with 16-player squads. Every name is invented; squads outside the featured fixture come from name pools, seeded so the same world is generated every time. Each player has a top speed (30-36 km/h), passing, finishing, and work rate, and these feed the simulation.

## The engine

`backend/app/generator/engine.py` simulates a match in **0.2-second ticks**:

- **Movement.** Every player moves toward a target with realistic acceleration (4 m/s²) and their own top speed. Targets come from the team's formation, shifted by the ball: compact and narrow out of possession (a low block near their own goal), wider in possession. Attackers make intermittent runs in behind; the nearest defender presses the ball while the next covers goal-side; a pass receiver runs onto the ball.
- **Decisions.** The ball carrier chooses when to pass, shoot, or keep going. Pass choice weighs progress, the receiver's space, and whether a defender blocks the lane; success depends on distance, pressure, the lane, the passer, and whether it goes into the final third. Shots depend on a location expected-goals (xG) model and on how many defenders stand between the shooter and goal.
- **Events and tracking stay consistent.** Events are emitted from the same simulation that moves the players, so the ball is always where the events say it is. Speeds, distance covered, and sprints (over 25.2 km/h for at least a second) come out of the movement rather than being invented. Tracking frames are recorded at 2.5 Hz and interpolated on request.
- **Stoppages.** Misplaced passes can run out of play (a throw-in after a short stoppage), fouls stop play for a free kick, and goals pause for the restart, so the ball is not in play for all 90 minutes.

## Storylines

`backend/app/generator/storylines.py` defines how a match should feel. A storyline has a **dominance curve** (who is on top, minute by minute) that tilts the engine's probabilities, and **beats** (goals or red cards that must happen near given minutes). Beats guarantee a demo match tells its story; dominance makes the play around them look earned.

| Storyline | What happens |
|---|---|
| `second_half_comeback` | Home lead early, away dominate after the break and win late (the featured demo match: 1-0 at 63', 1-2 at full time) |
| `late_collapse` | Home lead by two, then concede three in the last quarter of an hour |
| `red_card_swing` | A first-half red card for the home side swings the match |
| `dominant_but_wasteful` | Home have the chances and lose to one counter |
| `end_to_end` | Goals at both ends |
| `balanced` | No script |

A matchday (`matchday.py`) is 12 fixtures, each with its own seed and storyline. The whole matchday simulates in about 8 seconds.

## Validation

`backend/app/generator/validation.py` checks every match against the range of real top-flight football for a single match, per team and per match:

| Check | Range |
|---|---|
| Passes per team | 300-950 |
| Pass accuracy | 65-92% |
| Shots per team / per match | 2-38 / 10-50 |
| Tackles per team | 6-32 |
| Fouls per team | 1-22 |
| Pressures per team | 60-280 |
| Goals per match | 0-8 |
| Cards per match | 0-9 |
| Home possession | 25-75% |
| Median distance covered (outfield) | 9-13 km |
| Median sprints per player | 5-40 |
| Fastest sprint | 30-37.5 km/h |
| Median shot speed | 60-110 km/h |

Run it with `cd backend && uv run python -m app.generator.validation`.

**Result:** across five matchdays (60 matches, 1,200 checks), about 99% of checks pass, and the rare failures are near misses (for example 36 tackles against a ceiling of 32), the normal variance of a stochastic simulation. The tests require the demo matchday to pass at least 98% of its checks with every miss within 20% of its range, so a drift in realism fails CI.

Tuning went through several rounds against this report; each round fixed a modelling problem rather than a number. Examples: ball carriers dribbled through defences (they now only carry into space), teams recycled the ball near the box forever (passes into the final third are now harder), and "dominance" showed up as frantic pressing instead of possession (the dominant side now keeps the ball better and the dominated side presses less).

## Importance: expected threat (xT)

Every action stays in the data, but the screens and agents work from **importance**, computed by the aggregator (`backend/app/state/`).

- **The xT grid** (`xt.py`) gives each of 16 x 12 pitch zones the probability that possession there leads to a goal. It is learned from our own simulated matches (24 unscripted matches, about 32,000 passes and shots) with the standard value-iteration method: per zone, how often the team shoots, scores, and moves the ball to each other zone. The grid is mirrored left-right (football is symmetric) and smoothed where data is thin. Regenerate it with `uv run python -m app.state.xt`.
- **Each action's impact** (`aggregator.py`): a completed pass adds the threat difference between where it ended and started (forward passes matter; safe passes backwards barely do); a misplaced pass loses the threat the team had; a shot is worth its location xG; a tackle is worth the swing of winning the ball there.
- **Momentum** is each side's share of the threat created over the last few minutes (exponentially smoothed), from -1 (away on top) to 1 (home on top).
- **Key moments** are the defining plays: goals (with the shot as evidence), big chances (xG 0.15+), saves of good chances, red cards, decisive forward passes, balls won high up, and momentum shifts (the curve swinging to one side and staying there for three minutes). Each carries the event IDs that justify it.
