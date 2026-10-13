# Evaluations

Does a team of agents put better graphics on air than one agent doing the whole job? We measure it
on every moment of the featured match, with Microsoft Foundry's evaluators as the judge.

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

## Reproduce

```bash
make evals   # about 15 minutes and $2 of tokens; rewrites graphics.json and graphics.md
```

Needs the Foundry project in `backend/.env` (see `infra/README.md`). Each run also appears in the
Foundry portal under Evaluations, for anyone with access to the project.
