# Evaluations

Does a team of agents do better than one agent doing the whole job? We measure it twice, with
Microsoft Foundry's evaluators as the judge: the graphics team on every moment of the featured
match, and the whip-around's Watchers and Director on every cut of a session.

## How it works

`make evals` (`backend/app/evals/graphics.py`) takes the 39 moments the desk detects in the featured
match and gives each one, as the same brief, to two systems:

- **The graphics team** (`backend/app/agents/team.py`): Interpreter, Explainer (with the Foundry IQ
  knowledge base), a code checker, a fact-checker, Producer, Localizer. Either checker sends a draft
  back to the Explainer, up to three drafts; a moment that never passes airs the scripted copy.
- **A single agent** (`backend/app/evals/solo.py`): the same model (gpt-5.4-mini), the same brief,
  the same knowledge base with the same single lookup, and the four specialists' instructions word
  for word, plus the checkers' rules as instructions to check its own work. Nobody sends its draft
  back.

Then, for both:

- **The code checker** holds each answer to its brief: every claim cites events in the brief, and
  every number and name comes from them. Could it air with its receipts?
- **Foundry's evaluators** judge what each would put on air (the English headline and body) against
  the brief and whatever the writer's knowledge-base lookup returned: groundedness, relevance,
  coherence, each 1-5. The judge is gpt-6-luna, a different model from the writers, so neither side
  is marked by its own model.

Every answer, check, score, and the judge's reasons are in [graphics.json](graphics.json); the
summary and the moment-by-moment table are in [graphics.md](graphics.md).

## Results

| | Graphics team | Single agent |
|---|---|---|
| Graphics put on air | 39 | 39 |
| On air with an unsupported citation, number, or name | **0** | 5 (13%) |
| Foundry groundedness | **4.77** (37/39 pass) | 4.69 (36/39 pass) |
| Foundry relevance | **4.33** (39/39 pass) | 4.23 (38/39 pass) |
| Foundry coherence | 4.00 | 3.97 |
| Median seconds per moment | 10.1 | **5.0** |
| Mean tokens per moment | 8,997 | **7,190** |

Generated 2026-10-13 on matchday `73e2d515d426`.

**What a single agent can't do here is check its own work.** Told the same rules, it still put 5
graphics on air with a number, citation, or name its brief doesn't support. The team put none: the
code checker sent 15 drafts back and the fact-checker 7, and every moment still got a graphic. On
Foundry's judgement of meaning the two are level (one graphic apart), and the team is a little more
relevant. The price is time and tokens: about twice as long per moment, though the slowest run
(18.5 s) is well inside the 60 seconds the desk gives the team before airing its scripted copy.

## What the first run found

The first run (commit `0c03d33`) told a different story, and changed the team:

| First run | Graphics team | Single agent |
|---|---|---|
| On air with an unsupported citation, number, or name | 0 | 3 |
| Foundry groundedness | 3.68 (27/38 pass) | 4.10 (30/39 pass) |

The code checker kept wrong numbers and citations off air, but Foundry's judge found statements
with the right names and numbers in the wrong relation: which club had more of the ball, the order
of events, who passed to whom, a scoreline read backwards, "caught offside again" on the first
offside. Code can't see those. The team also made one error a single agent doesn't: the Explainer
followed the Interpreter's angle when the angle was wrong.

What changed, for both systems:

- **Clearer briefs.** Each club's stats on its own line by name, and a line saying which club is
  ahead on each; who leads, and stoppage time; events in time order with the latest marked; "a pass
  to Lindqvist, who was caught offside" instead of "misplaced"; "Westmere's 2nd offside of the
  match".
- **One rule for why it matters:** only from the score, the stats, and the events, never a guess at
  intent, role, or style.

And for the team only:

- **A fact-checker agent** after the code checker. It gives every statement in the draft a verdict
  (supported, fair reading, unsupported, wrong); anything unsupported or wrong goes back to the
  Explainer with what the brief shows.
- **The angle cites its evidence**, and the Explainer is told the brief wins when they disagree.
- **A workflow fix the fact-checker exposed.** Agent Framework sends a message down all of a step's
  edges at once, so a step that changed the message it was sent could flip a sibling edge's
  condition. Each step now works on its own copy.

## Still open

The judge's two remaining team failures: "lead 1-0 at the break" at 44' (the half wasn't over), and
"Westmere's first move after the restart" (not in the brief). Both are the kind of slip the
fact-checker is there to catch, so its instructions are the next thing to tune.

## The whip-around: Watchers and a Director vs one agent

The channel's own question: one Watcher per match and a Director, or one agent watching all ten?
`python -m app.evals.whip` replays a session from 55' with the code's Director, recording every
cut it asks the Director agent about (23: twelve goals, eleven pressure calls, each with the
code's candidates). For each cut:

- **The team.** Each candidate's Watcher (gpt-6-luna) tells its match's story from that match's
  brief alone, as the Watchers do ahead of every cut; the Director (gpt-5.4-mini), given the
  candidates and their stories, picks one and writes why and what's at stake. Both are checked,
  with one redraft.
- **A single agent**, twice, because it gets one model: on the Director's fast model and on the
  Watchers' accurate one. Given all ten matches' briefs, the table, and the same candidates, it
  picks the cut, writes why and what's at stake, and tells the story, with both specialists'
  instructions word for word and the checker's rules to check its own work.

The channel's checker holds each to its briefs; Foundry's evaluators judge what each would put on
air against the chosen match's brief; and the clock matters: the Director has a countdown (5 s,
3 s for a goal) and can still reword the cut for 15 s after it.

| 23 cuts | Watchers + Director | Single agent, fast model | Single agent, accurate model |
|---|---|---|---|
| On air with something the checker rejects | **0** | 8 | **0** |
| Foundry groundedness | **4.82** (21/22 pass) | 3.75 (12/20 pass) | 4.77 (21/22 pass) |
| Foundry relevance | **4.59** | 4.20 | 4.55 |
| Decided before the countdown ends | 18/23 (78%) | 20/23 (87%) | 0/23 |
| Worded in time (countdown + 15 s) | 23/23 | 23/23 | 23/23 |
| Median seconds to the cut | 2.8 | 2.8 | 12.8 |
| Mean tokens per cut | **8,236** | 8,446 | 9,645 |

Generated 2026-10-15 on matchday `73e2d515d426`; every answer and the judge's reasons are in
[whip.json](whip.json), the summary in [whip.md](whip.md).

**One agent can be fast or careful; the team is both.** On the fast model, a single agent decides
in time but puts something the checker rejects on air on 8 of 23 cuts and grounds worst. On the
accurate model it grounds as well as the team, but never decides inside the countdown: reading
ten matches takes it a median 12.8 s. The team splits the work so each part gets the model it
needs: the Watchers take the accurate model ahead of the cut, off the clock, and the Director
decides on the fast one with the stories in hand. When the checker sends a Director's draft back,
the cut goes ahead on time on the code's pick and the Director's words follow within the 15
seconds, which is why the team decides inside the countdown less often than the fast single
agent but words every cut in time. It also reads the least: each Watcher reads one match.

**What the earlier runs found.** The team's groundedness was 4.50 in the first run and 3.91 in
the second, and the judge's reasons showed why:

- The brief for a winner in the last second before full time described the table from before the
  goal (built at full time, it looked the table up rounded down to the second). In production,
  Ashby's 92nd-minute winner aired with "if Ironvale score next, Porthallow move into the top
  four" after Ironvale had scored. Fixed: tables for a moment round up.
- The Director, writing inside the countdown, gave matches where nothing rides on the next goal
  "the title picture". The checker now sends back a cut that talks about the table when its brief
  says nothing is at stake.
- The eval's own briefs listed stakes for matches already over (the table checked the live clock
  rather than its own moment). Fixed, for all three systems.

Caveats: one session of 23 cuts; the judge is gpt-6-luna, which is also the Watchers' model and
the accurate single agent's.

## Reproduce

```bash
make evals                                     # the graphics team: ~15 minutes, ~$2 of tokens
cd backend && uv run python -m app.evals.whip  # the whip-around: ~20 minutes, ~$2 of tokens
```

Needs the Foundry project in `backend/.env` (see `infra/README.md`). Each run also appears in the
Foundry portal under Evaluations, for anyone with access to the project.
