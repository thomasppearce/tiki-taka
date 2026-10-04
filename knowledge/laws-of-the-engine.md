# The laws the match engine enforces

These are the rules every simulated Match Desk match is played under. They follow the spirit of
the real laws of the game, simplified where the simulation needs it.

## Offside

- A player is in an offside position if, when a teammate passes to them, they are in the
  opponent's half and nearer the goal line than both the ball and the second-last opponent
  (usually the last outfield defender, with the keeper behind).
- Level is onside. The engine flags a player only when they are more than
  0.25 m beyond the line, the smallest margin an assistant would see.
- Offside is judged at the moment the pass is played, not where the ball is received.
- There is no offside from a throw-in, a goal kick, or a corner.
- An offside is punished with a free kick to the defending side where the offside player stood.
- Forwards wait about 0.8 m onside, then time their runs; a run released
  late, or a defensive line stepping up together, is what gets them caught.

## Restarts and stoppages

The ball is dead while a restart is set up: nobody presses or tackles until it is taken. The ball
is fetched to the restart spot and the taker walks to it; nobody is moved instantly. With these
stoppages, the ball is in play for roughly 60 of the 90-odd minutes, as in real football.

| Restart | Ball dead for |
|---|---|
| Throw | 10-18 s |
| Goal kick | 18-28 s |
| Corner | 25-35 s |
| Free kick | 18-32 s |
| Kickoff after a goal | 65 s |

- A ball that crosses a touchline is a throw-in to the side that did not touch it last.
- A ball that crosses the goal line off an attacker is a goal kick; off a defender, a corner.
- Shots saved or blocked are sometimes turned behind for a corner, and crosses cleared near the
  goal line sometimes go behind for one too.
- A foul is a free kick where it happened, and may bring a yellow or red card.
- Substitutions are made during stoppages and add time to them.
- Keepers holding the ball in their own penalty area cannot be challenged.
- When a scripted storyline goal is still due at full time, the referee adds up to
  5 minutes.
