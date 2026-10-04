# Synthetic match data

Match Desk runs on football-realistic data it generates itself: no real match data, clubs, or players. This page explains how the generator works and how its realism is checked.

## The world

`backend/app/generator/world.py` builds three fictional leagues (Meridian League, Harbour Coast League, Ironvale League) of 8 clubs each, with 16-player squads. Every name is invented; squads outside the featured fixture come from name pools, seeded so the same world is generated every time. Each player has a top speed (30-36 km/h), passing, finishing, and work rate, and these feed the simulation.

## Tactics

`backend/app/generator/tactics.py` gives every club a **tactical profile**: a style a coach would recognise (possession, high press, low block and counter, direct, balanced) plus nine dials from 0 to 1, with small per-club variations fixed by the seed. The dials are defensive line height, where pressing starts, pressing intensity, width with the ball, compactness without it, tempo, directness, use of the offside trap, and runs in behind. The featured fixture is a deliberate clash: Northgate Rovers' high possession line against Westmere Athletic's runners in behind.

The engine plays to these dials, and `python -m app.generator.knowledge` writes them up as prose in `knowledge/clubs/` (one page per club, with its squad), plus `knowledge/laws-of-the-engine.md`. Those pages go into the Explainer's search index, so an agent that says "Westmere keep getting caught by Northgate's high line" is citing the same profile the match was played from.

## The engine

`backend/app/generator/engine.py` simulates a match in **0.2-second ticks**:

- **Team shape.** Each side's back line moves as a unit: it steps up and drops together, about half a meter for every meter the ball moves, around a resting height set by the tactics. It drops further when the ball is in its own third or a runner goes in behind, unless the side likes to play the offside trap. The rest of the team keeps its formation relative to that line: compact and narrow without the ball, spread out with it, shifting toward the ball's side. Teams only reshape once a possession settles (1.5 s), so a turnover that is won straight back does not send 20 players back and forth, and the side that just lost the ball counter-presses in its attacking shape.
- **Off the ball.** The two teammates nearest the carrier offer angles (one short, one ahead). Forwards wait just onside, then make timed runs in behind; the runner shapes the run along the line before bursting, and the carrier looks to release it before it strays offside. The nearest defender presses (if the ball is inside the zone where that side presses) and the next covers. Players caught upfield make recovery runs, and the side that wins the ball breaks forward; how hard each player runs in each transition varies.
- **Movement.** Players react to the play with a short lag (quicker for hard workers), accelerate the way athletes do (hard from a standstill, gently near top speed, so top speeds vary from sprint to sprint), brake to arrive, walk small adjustments rather than jogging them, and sway gently when the play is elsewhere.
- **Decisions.** The ball carrier carries into the most open forward lane and decides when to pass, shoot, or keep going. Pass choice weighs progress, the receiver's space, whether a defender blocks the lane, the side's directness, and runs in behind (through balls are played into the space ahead of the runner). Success depends on distance, pressure, the lane, the passer, and whether it goes into the final third. Shots depend on a location expected-goals (xG) model and on how many defenders stand between the shooter and goal; players also strike from range when space opens.
- **Laws.** Offside is judged at the moment of the pass (level is onside, no offside from throw-ins, goal kicks, or corners) and punished with a free kick. Balls over the touchline are throw-ins; over the goal line, goal kicks or corners depending on who touched it last; saves and blocks are sometimes turned behind for corners. Fouls are free kicks, with cards. Keepers holding the ball in their own box cannot be challenged. Sides learn: each offside makes their runners wait a little deeper and their passers more careful.
- **Stoppages and continuity.** Restarts take as long as real ones (a throw-in 10-18 s, a goal kick 18-28 s, a free kick 18-32 s, a corner 25-35 s, a goal 65 s), substitutions are made during them, and nobody presses or tackles until the restart is taken. About 30 of the 90-odd minutes are stoppages, close to real football. **Nothing is ever moved instantly:** the ball is fetched to the restart spot, the taker walks to it and play waits for them, players walk back to their kickoff spots after a goal and at half-time. A test checks every frame of a matchday: no player ever moves faster than a sprinter, and the ball never faster than a shot.
- **Events and tracking stay consistent.** Events are emitted from the same simulation that moves the players, so the ball is always where the events say it is. Speeds, distance covered, and sprints (over 25.2 km/h for at least a second) come out of the movement rather than being invented. Tracking frames are recorded at 2.5 Hz; players are interpolated along smooth curves between frames (Catmull-Rom), the ball in straight lines.

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

A matchday (`matchday.py`) is 12 fixtures, each with its own seed and storyline. The whole matchday simulates in about 15 seconds. When a scripted goal is still due at full time, the referee adds up to five minutes.

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
| Offsides per team | 0-7 |
| Goals per match | 0-8 |
| Cards per match | 0-9 |
| Home possession | 25-75% |
| Median distance covered (outfield) | 9-13 km |
| Median sprints per player | 5-40 |
| Fastest sprint | 30-37.5 km/h |
| Median shot speed | 60-110 km/h |

Run it with `cd backend && uv run python -m app.generator.validation`.

**Result (2026-10-04):** across five matchdays (60 matches, 1,320 checks), 99.8% of checks pass; the two misses are near misses (a dominant side with 42 shots against a ceiling of 38). Averages per team: 534 passes at 82% accuracy, 15 shots, 1.5 goals, 1.4 offsides, 10 fouls; per outfield player, 11.2 km covered and 22 sprints, with the match's fastest sprint around 33 km/h. The tests require the demo matchday to pass at least 98% of its checks with every miss within 20% of its range, so a drift in realism fails CI.

Tuning went through several rounds against this report; each round fixed a modelling problem rather than a number. Examples:

- Ball carriers dribbled through defences (they now only carry into space).
- Teams recycled the ball near the box forever (passes into the final third are now harder).
- "Dominance" showed up as frantic pressing instead of possession (the dominant side now keeps the ball better, and the dominated side presses less).
- Players covered 17 km. Their shape followed the ball one-for-one, they jogged every small adjustment, and the ball was only dead for 5 minutes. Now the block shifts half as far, small moves are walks, and stoppages take as long as real ones.
- Every recovery run sat right on the sprint threshold, so sprint counts swung between 3 and 60 per player. Effort now varies per transition.
- Counter-attacking sides were caught offside 16 times. Passers now see clear offsides coming, and sides adapt after each flag.

## Importance: expected threat (xT)

Every action stays in the data, but the screens and agents work from **importance**, computed by the aggregator (`backend/app/state/`).

- **The xT grid** (`xt.py`) gives each of 16 x 12 pitch zones the probability that possession there leads to a goal. It is learned from our own simulated matches (24 unscripted matches, about 32,000 passes and shots) with the standard value-iteration method: per zone, how often the team shoots, scores, and moves the ball to each other zone. The grid is mirrored left-right (football is symmetric) and smoothed where data is thin. Regenerate it with `uv run python -m app.state.xt`.
- **Each action's impact** (`aggregator.py`): a completed pass adds the threat difference between where it ended and started (forward passes matter; safe passes backwards barely do); a misplaced pass loses the threat the team had; a shot is worth its location xG; a tackle is worth the swing of winning the ball there.
- **Momentum** is each side's share of the threat created over the last few minutes (exponentially smoothed), from -1 (away on top) to 1 (home on top).
- **Key moments** are the defining plays: goals (with the shot as evidence), big chances (xG 0.15+), saves of good chances, red cards, decisive forward passes, balls won high up, and momentum shifts (the curve swinging to one side and staying there for three minutes). Each carries the event IDs that justify it.
