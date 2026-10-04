# Match Desk: Project Brief for Claude Code

> Working name: **Match Desk**. Rename freely.
> Built for **Inside the Game: Developer Hackathon** (Microsoft x Premier League).
> Solo developer. Strong in Python, RAG, pipelines, data architecture, GCP, REST APIs. New to React/Next.js and Azure agent tooling, so explain non-obvious frontend and Azure choices briefly as you go.

---

## 1. What we are building

A **live broadcast control room**. Synthetic football match events stream in; a team of AI agents proposes broadcast-ready graphics and commentary lines; each proposal carries **evidence** (the exact events that justify it); a human producer **approves, edits, or rejects** it; approved items are emitted as **timed, machine-readable overlay JSON** and rendered on a mock broadcast preview.

One-line pitch: *"Every graphic on air has receipts, and a human in the loop."*

### Product structure (decided 2026-10-04)
- **Match centre (home, `/`):** live scores for **3 fictional leagues x 4 matches** (24 fictional clubs). Each card is a preview: score, minute, a mini momentum ribbon, and the match's single biggest moment. Clicking opens the match.
- **One featured match runs the full AI agent team.** The other 11 run the deterministic match engine and aggregator only (scores, momentum, key moments, no LLM cost).
- **Three ways to watch a match (`/match/[id]`), via an open role switch** in the top bar, clearly labelled as a demo switch. Sign-in is simulated, not real auth:
  - **Guest** (not signed in): broadcast view with approved graphics in the default feed, a lighter data layer, and a prompt to sign in for more (the sign-up hook).
  - **Fan** (signed in, demo account): full personalization via their `ViewerProfile` (audience, language, favorite club, player focus, spotlight metric) and the full data panels.
  - **Producer** (admin): the control room for the featured match: proposal queue, approve/edit/reject, agents, audit trail.
- The headline demo shot: split screen, the producer approves on the left and the fan's broadcast updates on the right.

### Importance: expected threat (xT)
Every action stays in the data (realism and aggregates need it), but screens and agents work from **importance**, computed by the aggregator from an **expected-threat (xT)** model: each pitch zone has a value (how likely possession there leads to a goal). An action's importance is the threat it added or removed; **momentum** is each team's rolling threat; the **most defining plays** are the biggest swings. One transparent model drives the key-play trail, timeline markers, home-page highlights, and the Interpreter's moment detection, and every importance score is explainable.

### Core pipeline (mirrors the hackathon brief)
1. **Ingest** synthetic match events as they happen
2. **Interpret** into stats, patterns, and key moments
3. **Explain** why a moment matters (with cited event IDs)
4. **Render** into overlay JSON + on-screen graphics
5. **Personalize** (Analyst vs Casual Fan, language, favorite club/player, **player-focus mode**, **spotlight metric**)

### Target prizes
- Primary: **Best Multi-Agent System**, **Best Use of Microsoft Foundry**
- Secondary: **Best Enterprise Solution** (audit trail, approvals, evidence, observability)
- Also competing for Grand Prize, so the whole thing must feel like one polished product.
- Prizes are two Grand Prizes (1st, 2nd) plus four category prizes: Best Use of Microsoft Foundry, Best Enterprise Solution, Best Multi-Agent System, and Best Azure Cloud Native Integration (AKS, Container Apps, Functions, Logic Apps, AI data platforms). A project can win **at most 1 Grand + 1 Category** prize, so "Adherence to Category" (20%) is scored against whichever category we pick.
- Multi-agent judging asks for distinct roles, shared state, effective handoffs, failure recovery, and "an end-to-end outcome **a single agent could not achieve as effectively**". The demo and README must argue that last point explicitly.

---

## 2. Hackathon constraints (non-negotiable)

- Registration: Sep 29 to **Oct 20, 2026, 12:00 PM PT** (register at https://aka.ms/insidethegame).
- Submission period: **Oct 6 to Oct 27, 2026, 11:59 PM PT**. Target submitting by **Oct 26**.
- Judging: Oct 27 to **Nov 10, 2026**. Winners announced by Nov 20.
- Must be a **new project**, created after the start of the **Registration Period (Sep 29, 2026)** (Official Rules §4.3). Building before Oct 6 is allowed. Keep the repo history clean anyway (judges see it).
- **Public GitHub repo** required.
- **Demo video under 2 minutes**, public URL (YouTube/Vimeo). No copyrighted music or third-party trademarks (no Premier League marks in the UI or video).
- Must work and be accessible to judges free of charge **until the Judging Period ends (Nov 10, 11:59 PM PT)**. Budget hosting for that full window. Include test instructions (and credentials if gated).
- **Synthetic, football-realistic data only.** No real match footage or data. No real club badges, logos, or kits. Use fictional clubs/players.
- All materials in English.
- Judged equally (20% each) on: Technological Implementation, Agentic Design & Innovation, Real-World Impact, UX & Presentation (balanced frontend + backend), Adherence to Category.
- Judges reward visible use of Microsoft "hero tech": **Microsoft Foundry, Microsoft Agent Framework, Azure MCP, GitHub Copilot agent mode, Fabric, GitHub SDK, GitHub CLI, Azure Apps and AI Services, Azure AI Search, Azure databases, Container Apps / Functions**. Name and show these in the README, architecture diagram, and video.
- Judging Stage One is pass/fail on theme fit and use of the required technologies, so Foundry and Agent Framework must be obvious within seconds of the video.
- Source of truth: [`OFFICIAL RULES.md`](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md). Research notes, pinned versions, and setup checklist: [docs/prep-notes.md](docs/prep-notes.md).

---

## 3. Tech stack

| Layer | Choice |
|---|---|
| Backend / agents | **Python 3.12** (managed with `uv`), **FastAPI**, **Microsoft Agent Framework** (Python: `agent-framework-core`, `agent-framework-foundry`, `agent-framework-orchestrations`) |
| Models / agent hosting / evals / tracing | **Microsoft Foundry** (`FoundryChatClient`, `FoundryEvals`) |
| Retrieval (RAG) | **Azure AI Search** (football/tactics knowledge + match history), optionally as a **Foundry IQ** knowledge base via `agent-framework-azure-ai-search` |
| State / history | **Azure Cosmos DB** (or Fabric if time allows) |
| Event ingest | In-process async queue first; **Azure Event Hubs** later if time allows |
| Live transport to UI | **Server-Sent Events (SSE)** via FastAPI's built-in `fastapi.sse.EventSourceResponse` (no `sse-starlette`) |
| Frontend | **Next.js (React) + TypeScript**, **Tailwind CSS v4**, **shadcn/ui**, **Motion** (the `motion` package, formerly Framer Motion; import from `motion/react`) |
| Pitch/timeline visuals | **SVG in React**, D3 helpers (scales/shapes) where useful |
| Shared types | Pydantic → JSON Schema → `json-schema-to-typescript` (recipe in [docs/prep-notes.md](docs/prep-notes.md) §6) |
| Hosting | Azure Container Apps (backend), **Azure Static Web Apps Free** with a Next.js static export (frontend). **Region: North Central US (`northcentralus`)** for every resource. |
| Models | **`gpt-5.4-mini` on a DataZoneStandard deployment** (200K TPM quota; GlobalStandard quota is 0 on this subscription). Fallback: `gpt-5-mini` GlobalStandard. Embeddings: `text-embedding-3-small` GlobalStandard. |
| Observability | OpenTelemetry / Application Insights, Foundry tracing |

**Important:** Foundry, Agent Framework, and Azure MCP APIs change quickly. **Do not guess SDK names, method signatures, or package versions.** Check current official docs (Microsoft Learn / the package's repo) before writing integration code, and pin versions in `backend/pyproject.toml` (locked by `uv.lock`) / `frontend/package.json`.

**Agent Framework's Python API was renamed heavily in 2026.** Most tutorials, blog posts, and autocomplete still use removed names: `ChatAgent` is now `Agent`, `AzureAIAgentClient` is now `FoundryChatClient` / `FoundryAgent`, `thread` is now `session`, and `run_stream()` is now `run(stream=True)`. Never install `agent-framework-azure-ai` (removed). See the cheat sheet in [docs/prep-notes.md](docs/prep-notes.md) §4.

---

## 4. Architecture

```
Synthetic match generator (Python)
        |  timed events
        v
FastAPI backend ── state aggregator (possession, pressure, rhythm, player stats)
        |
        v
Agent team (Microsoft Agent Framework on Foundry)
  Interpreter -> Explainer -> Producer -> Localizer/Personalizer -> Renderer
        ^                 (Orchestrator: shared state, handoffs, retries)
        |
   Azure AI Search (RAG) + Cosmos DB (match state, proposals, audit log)
        |
        v  SSE stream: events, state, proposals, decisions
Next.js control room  <--->  REST: approve / edit / reject / settings
        |
        v
Overlay JSON -> mock broadcast preview (animated lower-thirds, stat bars, player tags)
```

### Agent roles
| Agent | Responsibility |
|---|---|
| **Interpreter** | Reads aggregated state; detects key moments (momentum shifts, pressure spikes, milestones, tactical changes, **player speed/distance thresholds**). Emits structured "moment" objects with event IDs. |
| **Explainer** | Builds "why it matters" using RAG + match history. **Every claim must cite event IDs.** Refuses to assert anything it cannot ground. |
| **Producer** | Ranks and throttles proposals so the queue is never flooded; assigns type, priority, and a relevance expiry. |
| **Personalizer / Localizer** | Produces variants per audience (Analyst, Casual Fan), favorite club/player emphasis, and language (start with 2-3 languages). Applies the feed's `ViewerProfile` (5.6): in **player-focus mode** it boosts and reframes proposals around the focus player; it attaches the viewer's **spotlight metric** to every overlay. |
| **Renderer** | Converts approved proposals into overlay JSON with timing and style. |
| **Orchestrator** | Shared state, handoffs, retries, failure recovery. Must be able to **demo one agent failing and the system recovering**. |

Constrain agent outputs with **structured/JSON-schema outputs**. No free-form narration without citations.

---

## 5. Data contracts (define first; everything hangs off these)

Share types between Python (Pydantic) and TypeScript. Generate TS types from the Pydantic models or JSON Schema so they never drift.

### 5.1 MatchEvent
```json
{
  "event_id": "evt_000412",
  "match_id": "m_001",
  "minute": 71,
  "second": 14,
  "match_clock_ms": 4274000,
  "type": "pass | shot | tackle | possession_change | pressure | foul | card | substitution | goal | save | sprint | kickoff | half_end",
  "team_id": "t_home",
  "player_id": "p_home_08",
  "target_player_id": "p_home_10",
  "location": { "x": 62.4, "y": 31.0 },
  "end_location": { "x": 78.9, "y": 40.2 },
  "outcome": "success | fail | blocked | saved | off_target | goal",
  "attributes": {
    "pass_distance_m": 18.4, "pass_difficulty": 0.62, "ball_speed_kmh": 62.0, "pressure_level": 0.7,
    "player_speed_kmh": 21.5, "distance_covered_m": 8140.0
  }
}
```
Pitch coordinates: 0-100 on both axes (normalized), x = attacking direction for the home team.

Attribute keys (all optional; which ones appear depends on `type`):
| Key | On | Meaning |
|---|---|---|
| `pass_distance_m`, `ball_speed_kmh` | pass | Pass quality inputs. Pass accuracy is aggregated from `outcome`. |
| `pass_difficulty` | pass | 0-1 rating from distance, pressure, angle, and whether it breaks a line. |
| `ball_speed_kmh` | shot | **Shot speed** (always present on shots). |
| `pressure_level` | any | 0-1 pressure on the actor. |
| `player_speed_kmh` | any | Actor's speed at the moment of the event. |
| `distance_covered_m` | any | Actor's cumulative distance this match (from the generator's per-player movement model). |
| `top_speed_kmh`, `sprint_distance_m` | sprint | High-intensity run (≥ 25 km/h) for speed tags. |

### 5.2 Moment (Interpreter output)
```json
{
  "moment_id": "mom_0087",
  "kind": "momentum_shift | pressure_spike | milestone | tactical_change | key_chance | control_vs_chaos | player_threshold",
  "match_clock_ms": 4274000,
  "summary": "Home side's field tilt jumps from 48% to 71% over 6 minutes",
  "metrics": { "field_tilt_before": 0.48, "field_tilt_after": 0.71 },
  "evidence_event_ids": ["evt_000398", "evt_000401", "evt_000412"]
}
```

### 5.3 Proposal (what appears in the producer's queue)
```json
{
  "proposal_id": "prop_0141",
  "moment_id": "mom_0087",
  "type": "stat_graphic | narrative_line | tactical_insight | player_tag | recap_beat",
  "priority": 0.82,
  "confidence": 0.9,
  "expires_at_clock_ms": 4334000,
  "headline": {
    "analyst": { "en": "Home side pinning them in", "es": "..." },
    "casual":  { "en": "...", "es": "..." }
  },
  "body": {
    "analyst": { "en": "...", "es": "..." },
    "casual":  { "en": "...", "es": "..." }
  },
  "claims": [
    { "text": "Field tilt rose from 48% to 71%", "evidence_event_ids": ["evt_000398", "evt_000412"] }
  ],
  "status": "pending | approved | edited | rejected | expired",
  "produced_by": ["interpreter", "explainer", "producer", "localizer"],
  "trace_id": "...",
  "player_id": "p_home_09"
}
```

### 5.4 OverlayCommand (emitted on approval; "machine-readable, timed")
```json
{
  "overlay_id": "ovl_0141",
  "proposal_id": "prop_0141",
  "profile_id": "feed_analyst_en",
  "template": "lower_third | stat_bar | player_tag | momentum_graph | scorebug_update",
  "start_clock_ms": 4276000,
  "duration_ms": 6000,
  "audience": "analyst | casual",
  "language": "en",
  "payload": { "headline": "...", "stats": [{ "label": "Field tilt", "value": "71%" }] },
  "style": { "theme": "default", "animation_in": "slide_up", "animation_out": "fade" },
  "approved_by": "producer",
  "approved_at": "2026-10-12T19:04:11Z"
}
```

`player_threshold` fires when a player crosses a predefined threshold (e.g. a sprint above 32 km/h, passing 10 km covered). It becomes a `player_tag` proposal with the speed or distance indicator.

### 5.5 AuditRecord
Every proposal state change (created, approved, edited, rejected, expired, agent failure, retry) is logged with timestamp, actor (agent or human), and before/after. This powers the Enterprise story and a visible audit panel in the UI.

### 5.6 ViewerProfile (one per output feed)
```json
{
  "profile_id": "feed_analyst_en",
  "audience": "analyst | casual",
  "language": "en",
  "favorite_club_id": "t_home",
  "favorite_player_ids": ["p_home_10"],
  "focus_player_id": "p_home_10",
  "spotlight_metric": "pass_accuracy | pass_difficulty | distance_covered | top_speed | shot_speed | pressures"
}
```
- `focus_player_id` set means **player-focus mode**: proposals about that player are boosted, and the broadcast preview keeps a persistent player card.
- `spotlight_metric` is the "single performance metric a viewer cares about". The Personalizer adds it to every overlay for that feed.

### 5.7 TrackingFrame (synthetic tracking, streamed with events)
```json
{
  "match_id": "m_001",
  "match_clock_ms": 3792000,
  "ball": { "x": 18.0, "y": 38.0 },
  "players": [{ "player_id": "p_home_09", "team_id": "t_home", "x": 36.0, "y": 62.0, "speed_kmh": 21.4 }]
}
```
Where every player and the ball are at one instant (same normalized coordinates as MatchEvent). The generator emits frames at a few Hz alongside events; the control room interpolates them so the program camera and the tactical view show the same formations moving in sync with the actions. Until the generator streams them, `frontend/lib/matchSim.ts` simulates them.

---

## 6. Synthetic data generator (a scoring opportunity, so do it well)

- Python module producing full matches (fictional clubs, 11 players each plus subs) as a **timed event stream** that can replay at 1x / 5x / 20x. It runs a whole **matchday: 3 fictional leagues x 4 matches**, each with its own seed and storyline.
- Fictional leagues, clubs, and players only: no names resembling real competitions, clubs, or players. Squads are generated deterministically from name pools.
- Realism: possession chains, plausible pass distances and success rates by zone, pressure events, shot quality by location, fouls/cards, set pieces.
- Physical model: per-player speed and cumulative distance covered, plus `sprint` events, so speed/distance tags have real inputs. Also pass difficulty on every pass and shot speed on every shot.
- Tracking frames (5.7): team shapes that shift with the ball and compact out of possession, receivers running onto passes. Consistent with the events (the ball is where the events say it is).
- **Scripted storylines** selectable by seed/config: e.g. `late_collapse`, `second_half_comeback`, `red_card_swing`, `dominant_but_wasteful`. These guarantee interesting moments for the demo.
- Deterministic by seed (reproducible demos and tests).
- Include a **validation step** (basic realism checks: pass accuracy range, shots per match, possession sums to 100%, outfield distance covered roughly 9-13 km per 90 min, top sprint speeds roughly 30-36 km/h, plausible shot speeds, etc.) and document it, since "optimized synthetic data creation" is explicitly judged.
- Also produce a small football-knowledge corpus (original text written for this project: tactical concepts such as pressing, field tilt, low block, transitions) to index in Azure AI Search for the Explainer. Do not copy copyrighted material.

---

## 7. Frontend / UX direction

UI polish is a top priority (UX & Presentation is 20% of the score and the rubric explicitly wants a balanced frontend/backend).

**Routes:** `/` match centre; `/match/[id]` the match for Guest/Fan; the Producer role on the featured match shows the control room below. (Static export: match ids come from the fixed matchday list via `generateStaticParams`.)

**Color rule for many clubs:** data views encode by **role** (home = blue, away = aqua, validated for CVD) whichever clubs are playing. A club's own brand colors appear only on its crest and scorebug strip.

**Producer control room layout (desktop-first, dark control-room aesthetic):**
1. **Center: live pitch + timeline.** 2D SVG pitch with animated event markers/passing lines. Below it, a scrubbable momentum timeline (flowing line/area chart) with moment markers.
2. **Right: proposal queue.** Cards with type, headline, confidence, priority, countdown to expiry. One-keystroke actions: **A** approve, **E** edit, **R** reject. Animated enter/exit.
3. **Left/top: broadcast preview.** Mock match-feed frame with scorebug. Approved overlays animate in (lower-thirds, stat bars, player tags, momentum graph).
4. **Evidence view:** selecting a card highlights its cited events on the pitch and timeline. This is the signature interaction.
5. **Audience controls (per feed `ViewerProfile`):** Analyst vs Casual Fan, language switcher, favorite club, **player-focus mode** (pick a player; the pitch highlights their events and the preview keeps a persistent player card), and a **spotlight metric** picker. The same moment re-renders with different depth, tone, and emphasis.
6. **Audit / agent activity panel** (collapsible): shows agent handoffs, failures/retries, and the decision log.

**Design rules:** build a tiny design system first (tokens for color, spacing, type). Restrained palette, strong typography, purposeful motion (Motion) rather than constant motion. Invest the most polish in (a) the pitch/timeline and (b) the overlay animations. Handle loading, empty, and error states. Use fictional club identities (own crests/colors).

---

## 8. Suggested repo structure

```
/
  CLAUDE.md                 # this file
  README.md                 # judge-facing: pitch, architecture diagram, tech used, run instructions
  Makefile                  # make install / types / test / lint / dev-backend / dev-frontend
  /backend
    /app
      main.py               # FastAPI app, REST + SSE
      /models               # Pydantic schemas (single source of truth)
      /generator            # synthetic match engine + storylines + validation
      /state                # aggregator (possession, field tilt, pressure, player stats)
      /agents               # interpreter, explainer, producer, localizer, renderer, orchestrator
      /rag                  # indexing + retrieval (Azure AI Search)
      /audit                # audit log
    /tests
    pyproject.toml, uv.lock # uv-managed, Python 3.12
  /frontend
    /app                    # Next.js app router
    /components             # Pitch, Timeline, ProposalCard, BroadcastPreview, AuditPanel...
    /lib                    # SSE client, generated types, i18n
    package.json
  /knowledge                # original football-knowledge corpus for RAG
  /infra                    # Bicep/azd or deployment scripts for Azure
  /docs                     # architecture diagram, schema docs, demo script
    /schema                 # contracts.schema.json, generated by `make types`
```

---

## 9. Build phases

**Phase 0: Skeleton (first day)**
- Repo, folders, linting/formatting, Pydantic models for 5.1-5.6, generated TS types.
- FastAPI hello-world with an SSE endpoint streaming fake events; Next.js page that consumes it.

**Phase 1: Walking skeleton end to end (finish by ~Oct 12)**
- Generator -> aggregator -> **Interpreter** -> one hardcoded-quality proposal -> approve in UI -> overlay JSON -> animated overlay in preview.
- Pitch and timeline rendering with fake and then generated data. Prototype these early; they are the new-skill risk.

**Phase 2: Intelligence (by ~Oct 19)**
- Explainer with RAG and mandatory event-ID citations; Producer ranking/throttling.
- Personalizer/Localizer (Analyst/Casual, 2-3 languages); recap generation.
- Evidence view, edit flow, audit panel.

**Phase 3: Hardening and polish (by ~Oct 26)**
- Failure injection + recovery demo; tracing and evals in Foundry (e.g., check that every claim's cited events actually support it).
- Deploy to Azure (Container Apps etc.); README with architecture diagram; demo script; record the <2 min video; submit with buffer.

---

## 10. Scope guardrails

**In:** control room UI, 4-5 proposal types, evidence view, audience toggle, 2-3 languages, human approval + audit log, one demonstrated agent failure/recovery, deployed demo. Also, because the official challenge names them explicitly: player-focus mode, spotlight metric, threshold-triggered player speed/distance tags, pass difficulty rating, shot speed, and visible match recaps.

Also in: the match centre (3 leagues x 4 matches), the Guest / Fan / Producer role switch with simulated sign-in, and the xT importance model.

**Out (do not build):** video-based auto-eventing, many languages, real user accounts/auth (sign-in is simulated; Microsoft Entra External ID is a stretch goal only if everything else is done), anything that will not appear in the 2-minute demo video.

**Test for every feature:** *Does it show up in the demo video or earn judging points?* If not, cut it.

---

## 11. Engineering conventions

- Python: type hints everywhere, Pydantic v2 models, `ruff` + `black`, `pytest` for generator, aggregator, and schema tests.
- TypeScript: strict mode, ESLint + Prettier, shared generated types, no `any` without a comment.
- Small, frequent commits with clear messages (the repo history is visible to judges).
- Keep secrets in env vars / Azure Key Vault; commit a `.env.example`, never real keys. The repo is public.
- Document as you go: docstrings on agents and schemas, short ADRs in `/docs` for key decisions.
- Prefer boring, reliable solutions over clever ones; a working end-to-end demo beats an ambitious half-built design.
- When uncertain about an Azure/Foundry/Agent Framework API, **look it up in current docs rather than guessing**, and note the source in a code comment.

---

## 12. Open items

Resolved (2026-10-03):
- Starter resources: the official repo has only rules and learning playlists. **No sample data or schemas**, so we generate our own.
- Rules read in full. Findings are folded into sections 1 and 2 above and detailed in [docs/prep-notes.md](docs/prep-notes.md) §1.

Still open:
- Registered on Innovation Studio (2026-10-03). When submissions open (Oct 6), use "Create project" to see the exact submission fields and whether a category must be chosen. Also review the site's **Challenges** tab for any detail beyond the official rules.
- Azure subscription is **pay-as-you-go with no credit or spending cap**. Model quota checked, region chosen, resource providers registered, and a $50/month budget alert set (2026-10-03). Remaining: deploy the models via IaC. Default to free tiers and scale-to-zero (cost rules in [docs/prep-notes.md](docs/prep-notes.md) §8).
- Re-read the rules page for amendments (Section 11.5 allows changes at any time).
- Optional live sessions: Oct 14 (AKS and ACA) and Oct 21 (Azure Databases incl. Cosmos DB vector search), 4:00-5:00 PM UTC.

---

## 13. First task for Claude Code

1. Read this file fully.
2. Scaffold the repo structure in section 8 (empty modules with docstrings are fine).
3. Implement the Pydantic models from section 5 and generate matching TypeScript types.
4. Stand up the FastAPI SSE endpoint streaming fake `MatchEvent`s, and a Next.js page that renders them in a basic list.
5. Report what was created, how to run it, and propose the next three tasks.
