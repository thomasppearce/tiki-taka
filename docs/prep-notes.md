# Prep Notes (researched 2026-10-03)

Pre-build research for Tiki-Taka (then called Match Desk): rule findings, accounts to set up, pinned versions, current Agent Framework API, and the type-generation recipe. Versions were read from PyPI/npm on 2026-10-03; re-check anything older than a week before pinning.

---

## 1. Official rules: what changes the plan

Source: [`OFFICIAL RULES.md`](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md) in `microsoft/insidethegamehackathon`.

| Finding | Rule | Impact |
|---|---|---|
| **We can build now.** | §4.3: "Projects must be newly created by the Entrant after the start of the Hackathon **Registration Period**" (Sep 29, 2026, 9:00 AM PT). | CLAUDE.md §2 says "built during the event / inside the hacking window". Too strict. Code written from Sep 29 on is eligible. Submissions open Oct 6. |
| **Registration closes Oct 20, 12:00 PM PT.** | §1 | Register at https://aka.ms/insidethegame now. |
| **Demo must stay up until Nov 10, 11:59 PM PT.** | §4.8: free, unrestricted access "until the Judging Period ends" (Nov 10). | Hosting budget covers ~5 weeks, not 3. See §8. |
| **A fourth category prize: Best Azure Cloud Native Integration** (AKS, ACA, Functions, Logic Apps, AI data platforms). | §4.2 | Missing from CLAUDE.md, which listed only three. A project wins at most **1 Grand + 1 Category** prize, so pick one category to optimize "Adherence to Category" (20%) against. |
| **Multi-agent criteria are explicit.** | §4.2: "distinct roles, coordinate through shared state and effective handoffs, recover from failures, and deliver an end-to-end outcome **a single agent could not achieve as effectively**." | The demo and README should argue the last clause directly. |
| **Hero tech list is longer.** | §6.2 adds **GitHub SDK, GitHub CLI, Azure Apps and AI Services** to the CLAUDE.md list. | Cheap wins: `gh` in the workflow, Copilot agent mode noted in README. |
| **Stage One is pass/fail on theme plus required tech.** | §6.1 | Foundry and Agent Framework must be obvious within seconds of the video. |
| **No third-party trademarks in the video.** | §4.4 | No Premier League marks in the UI or video. Fictional clubs only (already planned). |
| **No starter data or schemas.** | §4.7, repo contents | Repo has only rules plus [learning playlists](https://github.com/microsoft/insidethegamehackathon/blob/main/RESOURCE%20PLAYLISTS.md). We generate everything. |

**Live sessions** ([Reactor series S-1709](https://developer.microsoft.com/en-us/reactor/series/S-1709/)), both 4:00-5:00 PM UTC:
- **Oct 14:** Build AI-powered soccer insights apps with AKS and ACA
- **Oct 21:** ...with cloud-native Azure Databases (Azure SQL, PostgreSQL, Cosmos DB vector search)

---

## 2. Setup checklist

### Do now (no code)
- [x] Registered on Innovation Studio 2026-10-03. "Create project" unlocks when submissions open Oct 6. If sign-in ever fails with AADSTS50020: use a private window, signed in only with the registered personal account; if it persists, email hackathonsupport@microsoft.com with the Request ID.
- [x] Git identity set globally: Thomas Pearce, `217870324+thomasppearce@users.noreply.github.com` (GitHub noreply, so commits link to @thomasppearce without exposing a personal email).
- [x] Azure subscription created 2026-10-03, pay-as-you-go (no free credit). Set budget alerts. See §8.
- [x] CLIs installed 2026-10-03 into `~/.local/bin` (no Homebrew on this machine):

| Tool | Version | How it was installed |
|---|---|---|
| Python 3.12 | via `uv` (system Python is 3.9) | `uv python pin 3.12` in `/backend` |
| Node / npm | 24.21 / 11.19 | already present |
| `az` (Azure CLI) | 2.90.0 | pip in its own venv `~/.local/share/azure-cli-venv`, symlinked. (`uv tool install` fails: azure-cli depends on pre-release ranges that only pip accepts.) Upgrade: `~/.local/share/azure-cli-venv/bin/pip install -U azure-cli` |
| `azd` | 1.35.0 | GitHub release binary, Microsoft code signature verified |
| `gh` (also a listed hero tech) | 2.102.0 | GitHub release binary, SHA-256 verified |
| Docker | not installed | Optional. ACR remote builds avoid needing it locally. |

- [x] `az login` done (subscription `Azure subscription 1`, pay-as-you-go, spending limit off).
- [x] Resource providers registered 2026-10-03: CognitiveServices, Search, DocumentDB, App, ContainerRegistry, OperationalInsights, Insights, Web, ManagedIdentity, KeyVault.
- [x] `azd auth login` and `gh auth login` done (GitHub account `thomasppearce`, HTTPS).

### Once the subscription exists
- [x] Quota checked and region chosen: **North Central US** (§7).
- [ ] Create the **Foundry project** in `northcentralus` via `azd`/Bicep (not the portal).
- [ ] Deploy `gpt-5.4-mini` (DataZoneStandard) and `text-embedding-3-small` (GlobalStandard) via the same templates.
- [ ] Connect **Application Insights** to the Foundry project (enables Foundry tracing).
- [ ] Create **Cosmos DB with the free tier opted in at creation** (one per subscription).
- [ ] Create **Azure AI Search Free** and confirm semantic ranker / agentic retrieval is supported in that region.

---

## 3. Pinned versions (as of 2026-10-03)

### Backend (Python 3.12)
| Package | Version | Notes |
|---|---|---|
| `agent-framework-core` | 1.20.0 | GA. Workflows built in. |
| `agent-framework-foundry` | 1.14.0 | GA. `FoundryChatClient`, `FoundryAgent`, `FoundryEvals`, embeddings. |
| `agent-framework-orchestrations` | 1.3.0 | Sequential / Concurrent / Handoff / GroupChat / Magentic builders. |
| `agent-framework-azure-ai-search` | 1.0.0b261002 | **Beta** (`--pre`). AI Search / Foundry IQ context provider. |
| `agent-framework-azure-cosmos` | 1.0.0b261002 | **Beta.** Includes `CosmosCheckpointStorage`. |
| `agent-framework-devui` | 1.0.0b261002 | **Beta**, dev-only debug UI. |
| `azure-ai-projects` | 2.7.0 | AF Foundry supports `>=2.2,<2.8`. |
| `azure-identity` | 1.26.0 | |
| `azure-search-documents` | 12.0.0 | |
| `azure-cosmos` | 4.17.1 | |
| `azure-monitor-opentelemetry` | 1.8.10 | |
| `fastapi` | 0.142.2 | **Native SSE** since 0.135 (`fastapi.sse`), so no `sse-starlette`. |
| `uvicorn` | 0.54.0 | |
| `pydantic` | 2.13.5 | |

**Avoid:**
- **`agent-framework-azure-ai`:** removed, frozen at rc6 (Mar 2026).
- **`azure-ai-agents`:** stale.
- **`azure-ai-inference`:** beta, untouched since Feb 2025.
- **`mcp`:** don't pin it independently. AF core requires `mcp<2` but the latest is 2.3.0, so let AF resolve it.

### Frontend
| Package | Version | Notes |
|---|---|---|
| `next` | 16.3.8 | |
| `react` | 19.3.0 | |
| `tailwindcss` | 4.3.3 | v4: CSS-first config, no `tailwind.config.js` by default. |
| `shadcn` (CLI) | 4.21.1 | |
| `motion` | 14.0.0 | Framer Motion's current name. Import from `"motion/react"`. |
| `d3-scale` / `d3-shape` | 4.0.2 / 3.2.0 | Stable for years. |
| `json-schema-to-typescript` | 16.0.0 | Type generation (§6). |
| `typescript` | 7.0.2 latest | TS 7 is the native-compiler release. Take whatever `create-next-app` installs. If ESLint tooling breaks, fall back to 6.x. |
| `eslint` / `prettier` | 10.12.0 / 3.9.9 | |

---

## 4. Agent Framework: current API (most online examples are stale)

The Python API changed heavily between late 2025 and mid 2026 ([breaking-changes guide](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes)). Blog posts, older samples and Copilot autocomplete will suggest the old names.

| Old (don't use) | Current |
|---|---|
| `ChatAgent` | `Agent` |
| `ChatMessage` | `Message(role=..., contents=[...])` |
| `AzureAIAgentClient`, `AzureAIClient` | `agent_framework.foundry.FoundryChatClient` / `FoundryAgent` |
| `AgentThread`, `get_new_thread()`, `thread=` | `AgentSession`, `create_session()`, `session=` |
| `agent.run_stream()` | `agent.run(..., stream=True)` |
| `model_id=` | `model=` |
| `WorkflowOutputEvent`, `RequestInfoEvent` | single `WorkflowEvent`; check `event.type == "output"` / `"request_info"` |
| `WorkflowBuilder().set_start_executor(...)` | `WorkflowBuilder(start_executor=..., checkpoint_storage=...)` |
| `response.try_parse_value(X)` | `response.value` (wrap in `try/except ValidationError`) |
| `.env` auto-loaded | **Not** auto-loaded: call `load_dotenv()` explicitly |

Foundry env vars: `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`, `FOUNDRY_EMBEDDING_MODEL`.

Structured output: `await agent.run(prompt, options={"response_format": MyPydanticModel})`, then `response.value`.

Observability: instrumentation is on by default. Call `configure_otel_providers()`, or `await agent.configure_azure_monitor()` for `FoundryAgent`.

---

## 5. Framework features that map onto our design (proposal, decide in Phase 1)

These are built-in features that would make the multi-agent story concrete rather than hand-rolled:

- **One workflow run per moment.** Interpreter emits a `Moment`, which starts a `WorkflowBuilder` graph: Explainer → Producer → Localizer → **human approval** → Renderer.
- **Producer approval as native HITL.** An executor calls `ctx.request_info(request_data=proposal, response_type=Decision)`. The UI's approve/edit/reject POST becomes `workflow.run(responses={request_id: decision})`. Never responding = expiry. ([HITL docs](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop))
- **Failure recovery via checkpoints.** `CosmosCheckpointStorage` saves workflow state, including pending approval requests. Demo: kill the backend mid-match, restart, and pending proposals re-appear from the checkpoint.
- **Localizer fan-out.** `ConcurrentBuilder` runs one participant per audience × language.
- **Explainer RAG.** `agent-framework-azure-ai-search` context provider over a **Foundry IQ** knowledge base (Azure AI Search underneath). Counts toward both "Best Use of Foundry" and AI Search hero tech.
- **Evals.** `evaluate_workflow()` + `FoundryEvals` for the "every claim's cited events support it" check.
- **MCP.** Expose match state / event lookup as an MCP server that the Explainer calls to verify citations (`MCPStreamableHTTPTool`). Hits the "MCP integration" line in Agentic Design. **Azure MCP Server** (`@azure/mcp` 2.0.5 stable, 3.0 in beta) is for dev-time provisioning via Copilot agent mode.
- **Stretch: Foundry hosted agents.** `agent-framework-foundry-hosting` is still beta. Don't depend on it.

---

## 6. Type generation: Pydantic → TypeScript (verified)

Tested end to end in a scratch project with `pydantic==2.13.5` and `json-schema-to-typescript@16.0.0`. Pipeline: Pydantic models, then one JSON Schema (`models_json_schema`), then `json-schema-to-typescript`. No extra Python dependency. `pydantic-to-typescript` does the same thing but hasn't been released since Nov 2024.

Three settings make the output clean:

```python
from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import GenerateJsonSchema, models_json_schema

class Contract(BaseModel):
    # Fields with defaults are always serialized, so they must be required in TS (not `status?:`).
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

class NoFieldTitles(GenerateJsonSchema):
    # Field titles make json-schema-to-typescript emit alias noise (`type X = number`).
    def field_title_should_be_set(self, schema) -> bool:
        return False

_, schema = models_json_schema(
    [(m, "serialization") for m in ALL_CONTRACTS], title="Contracts", schema_generator=NoFieldTitles
)
```

```bash
npx json-schema-to-typescript -i shared/contracts.schema.json -o frontend/lib/contracts.generated.ts \
  --unreachableDefinitions --additionalProperties false
```

- **Model nested maps as models.** `dict[Literal["analyst","casual"], ...]` collapses to `{[k: string]: ...}`, so `Proposal.body` should be an explicit `AudienceBody(analyst=..., casual=...)` model.
- **Drift check:** a CI step that regenerates and runs `git diff --exit-code`.

---

## 7. Model choice

The current catalog ([Foundry models](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure), updated 2026-09-21) runs through GPT-5.4 / 5.5 / 5.6 and GPT-6 / 6.1. All support structured outputs.

- **Default for every agent: `gpt-5.4-mini` on a DataZoneStandard deployment** (200K tokens/min of quota, no request needed). It's the small model marketed for structured-output reliability.

**Quota on our subscription (checked 2026-10-03, pay-as-you-go, new):**

| Model | GlobalStandard | DataZoneStandard |
|---|---|---|
| `gpt-5.4-mini` | **0** (needs a quota request) | **200K** ✅ |
| `gpt-5.4`, `gpt-5.5` | 0 | — |
| `gpt-5-mini` | 500K ✅ | — |
| `gpt-4.1-mini` | 200K ✅ | — |
| `text-embedding-3-small` | 1M ✅ | — |

Fallback chat model: `gpt-5-mini` on GlobalStandard. A larger Explainer model needs a quota request (portal: Foundry → Quota).

**Region: pick one where AI Search can be created and the Free tier supports semantic ranker + agentic retrieval.**
- **Excluded:** East US, East US 2, West US, Sweden Central, West Europe and Germany West Central are flagged "high demand" and **block new AI Search services** ([region table](https://learn.microsoft.com/en-us/azure/search/search-region-support)).
- **Passing every check** (model SKU offered, quota present, AI Search Free with semantic ranker + agentic retrieval):
  - US data zone: North Central US, South Central US
  - EU data zone: France Central, Switzerland North, Poland Central
- **Chosen: North Central US (`northcentralus`).** It's the closest passing region to the developer (the nearer East US / East US 2 are blocked for AI Search). Container Apps, Cosmos DB, AI Search, Foundry (AIServices S0), Container Registry, App Insights and Log Analytics all confirmed available there.
- **Budget:** `matchdesk-budget` created 2026-10-03. $50/month (Oct 2026 – Jan 2027), with email alerts at $25 actual, $50 actual, and $50 forecast.
- **Explainer:** move up to a larger model only if quality demands it and quota allows. GPT-5.5+ needs a quota request below Tier 5.
- **Latency:** these are reasoning models. Keep `reasoning_effort` low for live paths.
- **Tool calling on GPT-5.6:** use the Responses API, because Chat Completions can't combine tools and reasoning.
- **Pick on the day:** choose from what is actually deployable in your region and tier.

---

## 8. Hosting and cost through Nov 10

- **Subscription: pay-as-you-go from day one** (signed up 2026-10-03; the Microsoft account had already used its free trial).
  - No credit and **no spending cap**. Budget alerts notify but don't stop charges.
  - Always-free amounts still apply (below). Rough total estimate through Nov 10: **$20–50**, mostly model tokens, the container registry, and a warm backend during judging.
- **Cost rules:**
  - Stay on free tiers.
  - Scale the backend to zero during development.
  - No AI Search Basic, Event Hubs, or other always-on extras unless clearly needed.
  - Budget alerts at $25 and $50.
- **Cosmos DB free tier:** 1000 RU/s + 25 GB, free indefinitely.
- **Azure AI Search Free:** 50 MB and 3 indexes. Fine for the knowledge corpus. Semantic ranker on Free is region-dependent.
- **Container Apps:**
  - Free grant: 180k vCPU-s + 360k GiB-s + 2M requests per month.
  - Scale-to-zero is free, but judges hit a cold start.
  - One always-on 0.5 vCPU replica exceeds the grant (~1.3M vCPU-s/month). Expect a small monthly bill for a warm backend.
- **Frontend: static export.** The control room is client-rendered and fed by SSE, so a Next.js static export (`output: "export"`) on **Static Web Apps Free** avoids SSR hosting entirely.
- **Model tokens:** the main variable cost. Judges replaying matches drive it. A mini model keeps it small.

---

## 9. Brief vs CLAUDE.md: gaps worth closing

**Status: folded into CLAUDE.md on 2026-10-03** (§1, §4, §5.1, §5.2, §5.6, §6, §7, §10). The Innovation Studio "Challenges" tab matches rules §4.1 nearly verbatim, with no additional requirements.

Named in the challenge text (§4.1) but originally missing from CLAUDE.md:

- **Player-focused mode:** follow one player through the match.
- **"Single performance metric a viewer cares about":** a personalization option.
- **Threshold-triggered player tags** with speed and distance indicators.
  - Needs synthetic `player_speed_kmh` and `distance_covered_m`.
  - Cheap to generate, and it maps straight to the existing `player_tag` overlay.
- **Pass quality:** add a **pass difficulty rating** next to distance and accuracy.
- **Shot speed:** add `shot_speed_kmh` (ball speed is already there).
- **Match recaps:** "automated match recaps" appears three times in the challenge text. Make the `recap_beat` / half-time and full-time recap visible in the demo.

Auto-eventing from video stays out of scope (footage-rights risk, per CLAUDE.md §10).
